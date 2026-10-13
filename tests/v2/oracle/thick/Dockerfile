# The real-Oracle tests with Oracle's own client (python-oracledb's thick mode), on Oracle Linux 8: the family of
# RHEL 8, with Python 3.12, the oldest the project takes, and Oracle Instant Client from Oracle's own package source.
#
# Build it from the root of the repository, which is where pyproject.toml is read from:
#
#     docker build -f tests/v2/oracle/thick/Dockerfile -t dataprep-v2-thick .
#
# Run the tests in it against a database that is there, with the repository mounted so that nothing in it is
# written (V2_ORACLE_DSN names the database as the container sees it):
#
#     docker run --rm -v "$PWD":/repo:ro -e V2_ORACLE_THICK=1 \
#       -e V2_ORACLE_DSN=host:1521/service -e V2_ORACLE_USER=... -e V2_ORACLE_PASSWORD=... \
#       dataprep-v2-thick python3.12 -m pytest tests/v2/oracle -m oracle -o addopts="" -p no:cacheprovider -n 0
#
# Without V2_ORACLE_THICK the same run is in thin mode: the two are meant to be run side by side.
FROM oraclelinux:8
RUN dnf -y install oracle-instantclient-release-23ai-el8 \
 && dnf -y install oracle-instantclient-basic python3.12 python3.12-pip \
 && dnf clean all
COPY pyproject.toml /tmp/pyproject.toml
# What the project itself asks for, and what its v2 engine, its Oracle components and its tests ask for: read from
# pyproject.toml, so that there is one list.
RUN python3.12 -c "import subprocess, sys, tomllib; \
project = tomllib.load(open('/tmp/pyproject.toml', 'rb'))['project']; extras = project['optional-dependencies']; \
wanted = project['dependencies'] + [need for name in ('v2', 'v2-oracle', 'dev', 'excel', 'yaml') for need in extras[name]]; \
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *wanted])"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/repo
WORKDIR /repo
