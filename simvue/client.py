from concurrent.futures import ProcessPoolExecutor
import os
import pickle
import requests

from .utilities import get_auth

CONCURRENT_DOWNLOADS = 10
DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_TIMEOUT = 30

def downloader(job):
    """
    Download the specified file to the specified directory
    """
    try:
        response = requests.get(job['url'], stream=True, timeout=DOWNLOAD_TIMEOUT)
    except requests.exceptions.RequestException:
        return

    total_length = response.headers.get('content-length')

    with open(os.path.join(job['path'], job['filename']), 'wb') as fh:
        if total_length is None:
            fh.write(response.content)
        else:
            for data in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                fh.write(data)

class Client(object):
    """
    Class for querying Simvue
    """
    def __init__(self):
        self._url, self._token = get_auth()
        self._headers = {"Authorization": f"Bearer {self._token}"}

    def list_artifacts(self, run, category=None):
        """
        List artifacts associated with a run
        """
        params = {'run': run}

        try:
            response = requests.get(f"{self._url}/api/artifacts", headers=self._headers, params=params)
        except requests.exceptions.RequestException:
            return None

        if response.status_code == 200:
            return response.json()

        return None

    def get_artifact(self, run, name):
        """
        Return the contents of the specified artifact
        """
        params = {'run': run, 'name': name}

        try:
            response = requests.get(f"{self._url}/api/artifacts", headers=self._headers, params=params)
        except requests.exceptions.RequestException:
            return None

        if response.status_code == 200 and response.json():
            url = response.json()[0]['url']

            try:
                response = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
            except requests.exceptions.RequestException:
                return None
        else:
            return None

        try:
            content = pickle.loads(response.content)
        except:
            return response.content
        else:
            return content

    def get_artifact_as_file(self, run, name, path='./'):
        """
        Download an artifact
        """
        params = {'run': run, 'name': name}

        try:
            response = requests.get(f"{self._url}/api/artifacts", headers=self._headers, params=params)
        except requests.exceptions.RequestException:
            return None

        if response.status_code == 200:
            if response.json():
                url = response.json()[0]['url']
                downloader({'url': url,
                            'filename': os.path.basename(name),
                            'path': path})

    def get_artifacts_as_files(self,
                               run,
                               path=None,
                               category=None,
                               startswith=None,
                               contains=None,
                               endswith=None):
        """
        Get artifacts associated with a run & save as files
        """
        params = {'run': run}
        if category:
            params['category'] = category

        try:
            response = requests.get(f"{self._url}/api/artifacts", headers=self._headers, params=params)
        except requests.exceptions.RequestException:
            return None

        if not path:
            path = './'

        if response.status_code == 200:
            downloads = []
            for item in response.json():
                if startswith:
                    if not item['name'].startswith(startswith):
                        continue
                if contains:
                    if contains not in item['name']:
                        continue
                if endswith:
                    if not item['name'].endswith(endswith):
                        continue

                job = {}
                job['url'] = item['url']
                job['filename'] = os.path.basename(item['name'])
                job['path'] = os.path.join(path, os.path.dirname(item['name']))

                if os.path.isfile(os.path.join(job['path'], job['filename'])):
                    continue

                if job['path']:
                    os.makedirs(job['path'], exist_ok=True)
                else:
                    job['path'] = path
                downloads.append(job)

            with ProcessPoolExecutor(CONCURRENT_DOWNLOADS) as executor:
                for item in downloads:
                    executor.submit(downloader, item)
