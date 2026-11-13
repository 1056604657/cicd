# Run from repository root: make -f scripts/Makefile verify
.PHONY: verify java manifests
verify:
	python3 -m unittest discover -s tests -v
	python3 scripts/validate.py
	mvn -B -ntp -f demo-java/pom.xml verify
java:
	mvn -B -ntp -f demo-java/pom.xml verify
manifests:
	python3 scripts/validate.py
