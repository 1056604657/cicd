def call() {
    pipeline {
        agent { label 'trusted-promotion' }
        options {
            timestamps()
            disableConcurrentBuilds()
            timeout(time: 20, unit: 'MINUTES')
            buildDiscarder(logRotator(numToKeepStr: '100'))
            skipDefaultCheckout(true)
        }
        parameters {
            string(name: 'RELEASE_DIGEST', defaultValue: '', description: 'Tested immutable sha256 digest; promotion never rebuilds')
        }
        stages {
            stage('Checkout trusted automation') {
                steps {
                    deleteDir()
                    checkout scm
                    script {
                        if (!(params.RELEASE_DIGEST ==~ /sha256:[0-9a-f]{64}/)) { error('Invalid digest') }
                        sh 'python3 -c "from scripts.common import site, production_ready; production_ready(site())"'
                        def cfg = readJSON file: 'ci/site.json'
                        env.IMAGE_REPOSITORY = cfg.imageRepository
                        env.RELEASE_DIGEST = params.RELEASE_DIGEST
                    }
                }
            }
            stage('Verify build signature and test attestation') {
                steps {
                    withCredentials([usernamePassword(credentialsId: 'harbor-ci-read', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASSWORD'), file(credentialsId: 'cosign-build-public-key', variable: 'BUILD_PUBLIC_KEY'), file(credentialsId: 'cosign-test-public-key', variable: 'TEST_PUBLIC_KEY')]) {
                        sh 'bash scripts/verify-release.sh'
                    }
                }
            }
            stage('Open production approval PR') {
                steps {
                    withCredentials([string(credentialsId: 'github-gitops-pr-token', variable: 'GH_TOKEN')]) {
                        sh 'python3 scripts/release_pr.py --environment prod --digest "$RELEASE_DIGEST" --source-sha "$(cat artifacts/source-sha.txt)"'
                    }
                    echo 'Production approval happens on the protected GitOps PR. Argo CD performs CD after merge.'
                }
            }
        }
        post {
            always {
                archiveArtifacts allowEmptyArchive: true, artifacts: 'artifacts/*.json,artifacts/*.txt'
                deleteDir()
            }
        }
    }
}
