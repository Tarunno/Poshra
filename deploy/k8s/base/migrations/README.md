Migrations run as Argo CD PreSync hooks: Argo applies these Jobs and waits for
them to succeed before it rolls out the new pods, so a deploy can never reach a
database that is missing its schema. If a migration fails the sync stops and
the old version keeps serving.

The Jobs are part of the kustomization, so they carry the same image tag as the
Deployments in the same sync — the schema and the code that expects it always
match. They run on every sync, which is why each migrator records what it has
applied and skips it next time.
