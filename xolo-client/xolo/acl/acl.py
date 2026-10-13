# xolo/acl/acl.py
import os
from typing import List,Dict,Set,Any
from option import Option,NONE,Some,Result,Ok,Err
from threading import Thread
from xolo.utils.utils import Utils
import hashlib as H
import humanfriendly as HF
import json as J
import time as T
from xolo.log import Log

class AclDaemon(Thread):
 
    def __init__(self,acl:'Acl',key:str="xolo-acl",output_path:str="/mictlanx/xolo",filename:str="xolo-acl.enc",daemon:bool = True, name:str="xolo-acl",heartbeat="15min"):
        Thread.__init__(self,daemon=daemon,name=name)
        self.is_running = True
        self.heartbeat = HF.parse_timespan(heartbeat)
        self.acl = acl
        self.key = key
        self.output_path = output_path
        self.filename = filename
        self.last_checksum:Option[str] = NONE
        self.log            = Log(
            name                   = name,
            console_handler_filter = lambda x: True,
            interval               = 24,
            when                   = "h",
            path=os.environ.get("XOLO_LOG_PATH", "/log")
        )

    def run(self):
        while self.is_running:
            T.sleep(self.heartbeat)
            start_time = T.time()
            save_result = self.acl.save(key=self.key,output_path=self.output_path,filename=self.filename)
            if save_result.is_err:
                self.log.error({
                    "msg":str(save_result.unwrap_err())
                })
            else:
                value = save_result.unwrap()
                self.log.info({
                    "event":"ACL.SAVED",
                    "output_path":self.output_path,
                    "filename":self.filename,
                    "service_time":T.time() -start_time,
                    "ok": value
                })




class Acl(object):
    PERM_READ = "read"
    PERM_WRITE = "write"
    PERM_DELETE = "delete"
    PERM_MANAGE = "sys:manage"  # The "Owner" permission
    
    def __init__(
            self,
            roles:Set[str] = set(),
            resources:Set[str] = set(),
            permissions:Set[str] = set(),
            grants:Dict[str, Dict[str, Set[str]]] = {},
            key:str = "xolo-acl",
            output_path:str="/mictlanx/xolo",
            filename:str="xolo-acl.enc",
            heartbeat:str="15sec"
        ):
        self.__roles                                 = roles
        self.__resources                             = resources
        self.__permissions                           = permissions
        self.__grants:Dict[str, Dict[str, Set[str]]] = grants
        self.__daemon = AclDaemon(
            acl=self,
            key=key,
            output_path=output_path,
            filename=filename,
            heartbeat=heartbeat
        )
        self.__daemon.start()

    def add_role(self,role:str):
        if not role in self.__roles:
            self.__roles.add(role)
            self.__grants[role] = {}
    
    def add_resource(self,resource:str):
        if not resource in self.__resources:
            self.__resources.add(resource)
    
    def add_permission(self,permissions:str):
        if not permissions in self.__permissions:
            self.__permissions.add(permissions)
    
    def add(self, grants:Dict[str,Dict[str,Set[str]]]):
        for role,val in grants.items():
            self.__roles.add(role)
            for resource, permissions in val.items():
                self.__resources.add(resource)
                self.__permissions.union(set(permissions))
        self.__grants= {**self.__grants, **grants}
    # Remove
    def remove_role(self,role:str):
        if role in self.__grants:
            self.__grants.pop(role)
        self.__roles.discard(role)
    
    def remove_resource(self,resource:str):
        for key,value in self.__grants.items():
            if resource in value:
                self.__grants[key].pop(resource)
        self.__resources.discard(resource)

    def remove_permission(self,permission:str):
        for key,value in self.__grants.items():
            for resource,permissions in value.items():
                ps = set(permissions)
                ps.discard(permission)
                self.__grants[key][resource] = ps
        self.__permissions.discard(permission)
    # Get
    def get_roles(self)->Set[str]:
        return self.__roles
    
    def get_resources(self)->Set[str]:
        return self.__resources
    
    def get_permissions(self)->Set[str]:
        return self.__permissions
    # Authorized
    def grant(self,role:str, resource:str, permission:str):
        self.__roles.add(role)
        self.__resources.add(resource)
        self.__permissions.add(permission)
        defaultv =  {resource: set([permission])}
        self.__grants.setdefault(role,defaultv)
        self.__grants[role][resource].add(permission)
    
    def grants(self, grants:Dict[str, Dict[str, Set[str]]]):
        self.add(grants=grants)
        for user_id,resources_perms in grants.items():
            resources = self.__grants.setdefault(user_id,{})
            for resource_id,new_perms in resources_perms.items():
                perms = resources.setdefault(resource_id,set([]))
                self.__grants[user_id][resource_id] = new_perms | perms



        # self.__grants= {**self.__grants, **grants}
    
    def revoke(self, role:str, resource:str, permission:str):
        if role in self.__grants:
            xs = self.__grants[role]
            if resource in xs:
                perms = set(self.__grants[role][resource])
                perms.discard(permission)
                self.__grants[role][resource] = perms
    
    def revoke_all(self, role:str, resource:Option[str]= NONE):
        if role in self.__grants:
            if resource.is_none:
                self.__grants[role] = {}
            else:
                resource = resource.unwrap()
                if resource in self.__resources:
                    self.__grants[role][resource] = set()
    #  Check
    def check(self,role:str, resource:str, permission:str)->bool:
        _role_perms = self.__grants.get(role,{})
        _resource_perms = _role_perms.get(resource,set())
        return permission in _resource_perms
    
    def check_any(self,roles:List[str], resource:str, permission:str)->bool:
        for role in roles:
            x = self.__grants.get(role, {})
            y = x.get(resource,set())
            if permission in y:
               return True 
        return False
    
    def check_all(self,roles:List[str], resource:str, permission:str)->bool:
        res = []
        for role in roles:
            x = self.__grants.get(role, {})
            y = x.get(resource,set())
            if permission in y:
                res.append(True)
        return len(res) == len(roles)
    
    def which_permissions(self, role,resource)->Set[str]:
        return self.__grants.get(role,{}).get(resource,set())

    def show(self)->Dict[str, Dict[str, Set[str]]]:
        return self.__grants
    
    def claim_ownership(self, actor: str, resource: str):
            """
            Call this immediately when a user creates a new Folder/Bucket.
            It makes them the 'Owner'.
            """
            # We use the raw parent method because this is the genesis event
            self.grant(actor, resource, Acl.PERM_MANAGE)
            self.grant(actor, resource, Acl.PERM_READ)
            self.grant(actor, resource, Acl.PERM_WRITE)
            self.grant(actor, resource, Acl.PERM_DELETE)
        
    def grant_as_owner(self, actor: str, target_user: str, resource: str, permission: str) -> Result[bool, str]:
        """
        The SAFE way to grant permissions. 
        Checks if 'actor' has 'sys:owner' first.
        """
        # 1. REUSE your existing check() method logic
        # Check if the 'actor' (the person trying to share) is actually an owner
        if self.check(role=actor, resource=resource, permission=Acl.PERM_MANAGE):
            
            # 2. REUSE your existing grant() method logic
            self.grant(target_user, resource, permission)
            return Ok(True)
            
        else:
            return Err(f"Access Denied: User '{actor}' is not the owner of '{resource}'")
    
    def revoke_as_owner(self, actor: str, target_user: str, resource: str, permission: str) -> Result[bool, str]:
        """
        The SAFE way to revoke permissions.
        """
        # 1. Allow users to remove THEMSELVES (optional, but good UX)
        if actor == target_user:
            if permission == Acl.PERM_MANAGE and self._is_last_owner(resource):
                return Err("Cannot remove the last owner. Assign a new owner first.")
            self.revoke(target_user, resource, permission)
            return Ok(True)

        # 2. Check Ownership
        if self.check(role=actor, resource=resource, permission=Acl.PERM_MANAGE):
            # Safety: Don't allow revoking the last owner (prevents locking everyone out)
            if permission == Acl.PERM_MANAGE and self._is_last_owner(resource):
                return Err("Cannot remove the last owner. Assign a new owner first.")
            
            self.revoke(target_user, resource, permission)
            return Ok(True)
        else:
            return Err(f"Access Denied: User '{actor}' is not the owner of '{resource}'")

    def _is_last_owner(self, resource: str) -> bool:
        """
        Helper to ensure we don't accidentally delete the only admin.
        """
        # REUSE your existing show() method to inspect data
        count = 0
        all_grants = self.show() 
        for role, resources in all_grants.items():
            if resource in resources and Acl.PERM_MANAGE in resources[resource]:
                count += 1
        return count <= 1
    @staticmethod
    def __write_and_encrypt(secret_key:bytes, raw_data:bytes, output_path:str,full_path:str)->Result[bool,Exception]:
        res = Utils.encrypt_aes(key=secret_key, data= raw_data)
        if res.is_ok:
            if not os.path.exists(output_path):
                os.makedirs(name=output_path,exist_ok=True)
            with open(full_path,"wb") as f:
                data = res.unwrap()
                f.write(data)
            return Ok(True)
        else:
            return Err(res.unwrap_err())
    def save(self,key:str,output_path:str,filename:str="xolo-acl.enc")->Result[bool,Exception]:
        try:
            full_path = "{}/{}".format(output_path,filename)
            # if not os.access(full_path,os.F_OK) and not os.access(full_path,os.R_OK):


            # xolo = Xolo()
            secret_key            = bytes.fromhex(key)
            grants = {}
            hasher = H.sha256()
            for role,resources_perms_map in self.__grants.items():
                for resource,permissions in resources_perms_map.items():
                    if not role in grants:
                        grants[role] ={}
                    if not resource in grants[role]:
                        grants[role][resource] = list(permissions)
            obj = {
                "roles":list(self.__roles),
                "resources": list(self.__resources),
                "permissions": list(self.__permissions),
                "grants": grants
            }
            json_str = J.dumps(obj)
            raw_data = json_str.encode("utf-8")
            hasher.update(raw_data)
            current_checksum = hasher.hexdigest()
            if self.__daemon.last_checksum.is_none:
                self.__daemon.last_checksum = Some(current_checksum)
                Acl.__write_and_encrypt(
                    secret_key=secret_key,
                    raw_data = raw_data,
                    output_path = output_path,
                    full_path=full_path

                )
                return Ok(True)
            else:
                last_checksum = self.__daemon.last_checksum.unwrap()
                if last_checksum == current_checksum:
                    return Ok(False)
                else:
                    self.__daemon.last_checksum = Some(current_checksum)
                    Acl.__write_and_encrypt(
                        secret_key=secret_key,
                        raw_data = raw_data,
                        output_path = output_path,
                        full_path=full_path
                    )
                    return Ok(True)
                # print("Something went wrong {}".format(res.unwrap_err()))

        except Exception as e:
            return Err(e)
            # print(e)
        # with open(path, "w") as f:
            # J.dump(obj, f)

    @staticmethod
    def load(key:str, output_path:str="/mictlanx/xolo",filename:str="xolo-acl.enc",heartbeat="15min") -> Option["Acl"]:
        try:
            os.makedirs(output_path,exist_ok=True)
            path = "{}/{}".format(output_path,filename)
            with open(path, "rb") as f:
                secret_key            = bytes.fromhex(key)
                data = f.read()
                res = Utils.decrypt_aes(key=secret_key, data=data)
                if res.is_ok:
                    obj = J.loads(res.unwrap().decode("utf-8"))
                    grants = obj.get("grants",{})
                    for k1,v1 in grants.items():
                        for k2,v2 in v1.items():
                            grants[k1][k2] = set(v2)

                    acl = Acl(
                        roles       = set(obj.get("roles",set())),
                        resources   = set(obj.get("resources",set())),
                        permissions = set(obj.get("permissions",set())),
                        grants      = grants,
                        key=key,
                        heartbeat=heartbeat,
                        output_path=output_path,
                        filename=filename
                    )
                    return Some(acl)
                raise res.unwrap_err()
        except Exception as e:
            print(e)
            return NONE
                
    @staticmethod
    def load_or_create(key:str, output_path:str,filename:str="xolo-acl.enc",heartbeat="15min") -> "Acl":
        try:
            secret_key            = bytes.fromhex(key)
            if not os.path.exists(output_path):
                try:    
                    os.makedirs(output_path,exist_ok=True)
                except Exception as e:
                    print(e)
                    raise Exception("Cannot create output directory: {}".format(str(e)))
                
            path = "{}/{}".format(output_path,filename)
            if not os.path.exists(path=path):
                # f = open(path,"wb")
                data = J.dumps({
                    "grants":{}
                }).encode("utf-8")
                res = Acl.__write_and_encrypt(
                    secret_key  = secret_key,
                    raw_data    = data,
                    output_path = output_path,
                    full_path   = path
                )
                # print(res)
                if res.is_ok:
                    return Acl(heartbeat=heartbeat,filename=filename,output_path=output_path)
                raise Exception("Cannot encrypt and write your acl data. Try again")
                # f.close()
            else:
                f = open(path, "rb")
                data = f.read()
                res = Utils.decrypt_aes(key=secret_key, data=data)
                if res.is_ok:
                    obj = J.loads(res.unwrap().decode("utf-8"))
                    grants = obj.get("grants",{})
                    for k1,v1 in grants.items():
                        for k2,v2 in v1.items():
                            grants[k1][k2] = set(v2)

                    acl = Acl(
                        roles       = set(obj.get("roles",set())),
                        resources   = set(obj.get("resources",set())),
                        permissions = set(obj.get("permissions",set())),
                        grants      = grants,
                        key=key,
                        heartbeat=heartbeat,
                        output_path=output_path,
                        filename=filename
                    )
                    f.close()
                    return acl
                raise Exception("Descryption error: Check that you are using the correct key")
                # return Acl.load_or_create(key=key, output_path=output_path,filename="{}.enc".format(Utils.get_random_string(length=5)), heartbeat=heartbeat)
        except PermissionError as e:
            raise Exception("Permission error: Check that you have the right permissions to read/write in the output directory")
        except Exception as e:
            print(e)
            raise Exception("Error loading or creating ACL: {}".format(str(e)))
            
