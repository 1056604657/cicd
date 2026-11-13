# Bind only to service account vault-auth in namespace demo-prod on the PROD cluster.
path "kv/data/cicd/prod/harbor" { capabilities = ["read"] }
