use admin;
db.createUser({
  user: "xolo",
  pwd: "d22a75e9e729debc",
  roles: [{ role: "root", db: "admin" }]
});
mongosh -u xolo -p d22a75e9e729debc --authenticationDatabase admin