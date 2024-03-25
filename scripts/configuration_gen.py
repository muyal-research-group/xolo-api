import yaml
import pandas as pd


df = pd.read_csv("./users_prod.csv")
for i,row in df.iterrows():
    username = row["USERNAME"]
    password = row["PASSWORD"]
    print(username,password)
# Data to be written to the YAML file
    data = {
        'username': username,
        'password': password,
        'bucket_id': username,
        'folder_path': "./data",
        'mictlanx_routers': "mictlanx-router-0:alpha.tamps.cinvestav.mx/v0/mictlanx/router:-1",
        'mictlanx_protocol': "https",
        'sync_timeout': "30s",
        'sync_max_idle_time': "60s",
        'xolo_api_protocol': "https",
        'xolo_api_hostname': "alpha.tamps.cinvestav.mx/xoloapi",
        'xolo_api_port': -1,
        'xolo_api_version': 4,
        'chunk_size': "1MB"
    }

# File path where the YAML will be saved
    file_path = './out/config_{}.yml'.format(username)

# Writing data to the YAML file
    with open(file_path, 'w') as file:
        yaml.dump(data, file, default_flow_style=False)

    print(f"YAML file created at {file_path}")