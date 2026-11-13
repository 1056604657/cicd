# platform-ci Shared Library

Configure **Folder-level Pipeline Library** `platform-ci` with Modern SCM, this repository,
and Library Path `jenkins/shared-library`. Use a reviewed commit SHA as its default version;
disable version override. For stricter separation, move this directory to a dedicated library repository.
Do not mark an application-owned library as a globally trusted library.

Entry points:

- `javaServicePipeline(mode: 'check')`: untrusted source checks, no release credentials.
- `javaServicePipeline(mode: 'release')`: trusted main builds → image → test PR → read-only observation → signed test evidence.
- `promoteService()`: verifies immutable digest and evidence → production PR.

PR builds and trusted release jobs must be separate Jenkins folders/agent pools/credential scopes.
The check in Groovy is defense in depth, not a substitute for job isolation.
