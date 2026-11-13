# Bind only to service account vault-auth in namespace demo-test on the TEST cluster.
path "kv/data/cicd/test/harbor" { capabilities = ["read"] }
