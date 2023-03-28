def to_dataframe(data):
    """
    Convert runs to dataframe
    """
    import pandas as pd

    metadata = []
    for run in data:
        if 'metadata' in run:
            for item in run['metadata']:
                if item not in metadata:
                    metadata.append(item) 

    columns = {}
    for run in data:
        for item in ('name', 'status', 'folder', 'created', 'started', 'ended'):
            if item not in columns:
                columns[item] = []
            if item in run:
                columns[item].append(run[item])
            else:
                columns[item].append(None)
 
        if 'system' in run:
            for section in run['system']:
                if section in ('cpu', 'gpu', 'platform'):
                    for item in run['system'][section]:
                        if 'system.%s.%s' % (section, item) not in columns:
                            columns['system.%s.%s' % (section, item)] = []
                        columns['system.%s.%s' % (section, item)].append(run['system'][section][item])
                else:
                    if 'system.%s' % section not in columns:
                        columns['system.%s' % section] = []
                    columns['system.%s' % section].append(run['system'][section])

        if 'metadata' in run:
            for item in metadata:
                if 'metadata.%s' % item not in columns:
                    columns['metadata.%s' % item] = []
                if item in run['metadata']:
                    columns['metadata.%s' % item].append(run['metadata'][item])
                else:
                    columns['metadata.%s' % item].append(None)

    df = pd.DataFrame(data=columns)
    return df

def metrics_to_dataframe(data, xaxis, name=None):
    """
    Convert metrics to dataframe
    """
    import pandas as pd

    if name:
        columns = {xaxis: [], name: []}
        for item in data:
            columns[xaxis].append(item[0])
            columns[name].append(item[1])

        df = pd.DataFrame(data=columns)
    else:
        runs = []
        metrics = []
        for item in data:
            if item[2] not in runs:
                runs.append(item[2])
            if item[3] not in metrics:
                metrics.append(item[3])

        headers = pd.MultiIndex.from_product([runs, metrics, [xaxis, 'value']], names=["run", "metric", "column"])

        newdata = {}
        for row in data:
            if row[2] not in newdata:
                newdata[row[2]] = {}
            if row[3] not in newdata[row[2]]:
                newdata[row[2]][row[3]] = []

            newdata[row[2]][row[3]].append([row[0], row[1]])

        max_rows = 0
        for run in newdata:
            for metric in newdata[run]:
                if len(newdata[run][metric]) > max_rows:
                    max_rows = len(newdata[run][metric])

        results = []
        for count in range (0, max_rows):
            line = []
            for run in newdata:
                for metric in newdata[run]:
                    if count < len(newdata[run][metric]):
                        line.append(newdata[run][metric][count][0])
                        line.append(newdata[run][metric][count][1])
                    else:
                        line.append(None)
                        line.append(None)
            results.append(line)

        df = pd.DataFrame(data=results, columns=headers)
    return df
