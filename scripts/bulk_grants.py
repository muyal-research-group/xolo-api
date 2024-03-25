import pandas as pd
import json as J

with open("./imss_perms_050324.json",'r') as f:
    data = J.loads(f.read())
    grants = {}
    for x in data:
        username = x["username"]
        grants.setdefault(username, {} )
        for resource_acl in x["resources_acl"]:
            resource = resource_acl["resource"]
            perms = resource_acl["permissions"]
            grants[username].setdefault(resource,perms)
    print(grants)
    with open("./grants_req.json","w") as f2:
        f2.write(J.dumps(grants,indent=4))
    # print(data)


# df = pd.read_csv("./x.csv")
# xss= []
# with open("./y.json","w") as f:
#     data = []
#     for index,row in df.iterrows():
#         name = row["Nombre"]
#         username = row["Nombre de usuario"]
#         data.append((name,username))
#         xs = {
#             "resource":username,
#             "permissons":["read","write","update","delete"]
#         }
#         xss.append(xs)
#     ys=[]
#     for (name,username) in data:
#         y = {
#             "name":name,
#             "username":username,
#             "resources_ac":xss
#         }
    
#         ys.append(y)
#         # xs_str = J.dumps(xs)

#     f.write(J.dumps(ys,indent=4,ensure_ascii=True))

#         # print(name,username)
#         # print(row)
