def to_dataframe(data):
    """
    Convert runs to dataframe
    """
    import pandas as pd
    
    columns = {}
    for run in data:
        for item in ('name', 'status', 'folder', 'created'):
            if item not in columns:
                columns[item] = []
            columns[item].append(run[item])
 
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
            for item in run['metadata']:
                if 'metadata.%s' % item not in columns:
                    columns['metadata.%s' % item] = []
                columns['metadata.%s' % item].append(run['metadata'][item])

    df = pd.DataFrame(data=columns)
    return df
