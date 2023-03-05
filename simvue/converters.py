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
