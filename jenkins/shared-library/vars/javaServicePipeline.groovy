def call(Map options = [:]) {
    boolean publish = options.mode == 'release'
    pipeline {
        agent { label publish ? 'trusted-release-java21' : 'untrusted-check-java21' }
        options {
            timestamps()
            disableConcurrentBuilds()
            timeout(time: 100, unit: 'MINUTES')
            buildDiscarder(logRotator(numToKeepStr: '50', artifactNumToKeepStr: '20'))
            skipDefaultCheckout(true)
        }
        stages {
            stage('Checkout') {
                steps {
                    deleteDir()
                    checkout scm
                    script {
                        env.GIT_COMMIT = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                        if (publish && env.CHANGE_ID) { error('PR builds cannot publish') }
                    }
                }
            }
            stage('Tests and manifest policy') {
                steps {
                    sh 'python3 -m unittest discover -s tests -v'
                    sh 'python3 scripts/validate.py'
                    sh 'mvn -B -ntp -f demo-java/pom.xml verify'
                    sh 'mkdir -p artifacts && trivy fs --scanners secret --exit-code 1 --format json --output artifacts/source-scan.json --skip-dirs .git,demo-java/target .'
                }
            }
            stage('Publish immutable image') {
                when { expression { publish } }
                steps {
                    script {
                        // This is defense in depth. Job SCM/branch and credential ACLs are authoritative.
                        sh 'python3 -c "from scripts.common import site, production_ready; production_ready(site())"'
                        def cfg = readJSON file: 'ci/site.json'
                        env.IMAGE_REPOSITORY = cfg.imageRepository
                        env.RUNTIME_IMAGE = cfg.runtimeImage
                        withCredentials([usernamePassword(credentialsId: 'harbor-ci-push', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASSWORD')]) {
                            sh 'bash scripts/build-image.sh'
                            withCredentials([file(credentialsId: 'cosign-build-private-key', variable: 'COSIGN_KEY'), string(credentialsId: 'cosign-build-password', variable: 'COSIGN_PASSWORD')]) {
                                sh 'bash scripts/registry-sign.sh'
                            }
                        }
                    }
                }
            }
            stage('Open test GitOps PR') {
                when { expression { publish } }
                steps {
                    withCredentials([string(credentialsId: 'github-gitops-pr-token', variable: 'GH_TOKEN')]) {
                        sh 'python3 scripts/release_pr.py --environment test --digest "$(cat artifacts/image-digest.txt)" --source-sha "$GIT_COMMIT"'
                    }
                }
            }
            stage('Observe test deployment and attest') {
                when { expression { publish } }
                steps {
                    withCredentials([string(credentialsId: 'github-gitops-pr-token', variable: 'GH_TOKEN'), string(credentialsId: 'argocd-test-readonly-token', variable: 'ARGOCD_TEST_TOKEN')]) {
                        sh 'python3 scripts/verify_test.py'
                    }
                    withCredentials([usernamePassword(credentialsId: 'harbor-ci-push', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PASSWORD'), file(credentialsId: 'cosign-test-private-key', variable: 'TEST_SIGNING_KEY'), string(credentialsId: 'cosign-test-password', variable: 'COSIGN_PASSWORD')]) {
                        sh 'bash scripts/attest-test.sh'
                    }
                }
            }
        }
        post {
            always {
                junit allowEmptyResults: true, testResults: 'demo-java/target/surefire-reports/*.xml'
                archiveArtifacts allowEmptyArchive: true, artifacts: 'artifacts/*.json,artifacts/*.txt,demo-java/target/site/jacoco/**'
                deleteDir()
            }
        }
    }
}
