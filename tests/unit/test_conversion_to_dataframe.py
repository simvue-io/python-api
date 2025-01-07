from numpy import exp
from simvue.converters import to_dataframe

def test_run_conversion_to_dataframe():
    """
    Check that runs can be successfully converted to a dataframe
    """
    runs = [{'name': 'test1',
             'status': 'completed',
             'folder': '/',
             'created': '2023-01-01 12:13:14',
             'started': '2023-01-01 12:13:15',
             'ended': '2023-01-01 12:13:18',
             'metadata': {'a1': 1, 'b1': 'two'}},
            {'name': 'test2',
             'status': 'completed',
             'folder': '/',
             'created': '2023-01-01 12:14:14',
             'started': '2023-01-01 12:14:15',
             'ended': '2023-01-01 12:14:18',
             'metadata': {'a2': 1, 'b2': 'two'}}]

    runs_df = to_dataframe(runs)

    expected_columns = [
        'name',
        'status',
        'folder',
        'created',
        'started',
        'ended',
        'metadata.a1',
        'metadata.b1',
        'metadata.a2',
        'metadata.b2'
    ]

    assert sorted(runs_df.columns.to_list()) == sorted(expected_columns)

    data = runs_df.to_dict('records')
    for i in range(len(runs)):
        assert(runs[i]['name'] == data[i]['name'])
        assert(runs[i]['folder'] == data[i]['folder'])
        assert(runs[i]['created'] == data[i]['created'])
        assert(runs[i]['started'] == data[i]['started'])
        assert(runs[i]['ended'] == data[i]['ended'])
        for item in runs[i]['metadata']:
            index = f'metadata.{item}'
            assert(index in data[i])
            assert(runs[i]['metadata'][item] == data[i][index])
