#!/usr/bin/make
# Usage:
#   make        - same as 'make test'
#   make test   - start server, run localhost tests
#   make report - grab coverage
#
#   make gild   - start server, run localhost tests, write output to lead dir
#     after this, the expectation is that you will diff lead/gold dirs 
#     and copy over new & better pages to gold for checkin.
#

# path for coverage tool.  See http://nedbatchelder.com/code/coverage/
COVERAGE=coverage

# start webserver with a clear cache
APPSERVER=/usr/local/bin/dev_appserver.py \
  --admin_console_server= \
  --port=8080 \
  --clear_datastore \
  ../stockpredictr

# we need to wait for the server to start
SERVER_START_ALLOWANCE=5
SERVER_STOP_ALLOWANCE=5

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# main entry points
test:	start_webserver start_wait run_test stop_wait kill_webserver stop_wait stdoutcov

quick:	start_webserver start_wait run_quick_test stop_wait kill_webserver stop_wait stdoutcov

gild:	start_webserver start_wait run_gild stop_wait kill_webserver

report: htmlcov/index.html
	@open htmlcov/index.html

clean:
	rm -rf .coverage htmlcov lead/* server_output.txt

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# detailed entry points
run_test:
	@echo "Starting test..."
	@./test_localhost.py

run_quick_test:
	@echo "Starting test..."
	@./test_localhost.py TestBasics

run_gild:
	@echo "Starting test+gild..."
	@./test_localhost.py gild

htmlcov/index.html: .coverage
	@echo "Creating coverage html report"
	@${COVERAGE} html ../stockpredictr/*.py

stdoutcov:
	@${COVERAGE} report ../stockpredictr/*.py

start_webserver:
	@/bin/echo -n "Starting Server: "
	@date
	@${COVERAGE} run --branch ${APPSERVER} >& server_output.txt &

kill_webserver:
	@echo kill -15 `ps |grep dev_appserver.py |grep -v grep | cut -c 1-6`
	@kill -15 `ps |grep dev_appserver.py |grep -v grep | cut -c 1-6`

start_wait:
	@echo "giving the server "${SERVER_START_ALLOWANCE}" seconds to start..."
	@sleep ${SERVER_START_ALLOWANCE}

stop_wait:
	@echo "giving the server "${SERVER_STOP_ALLOWANCE}" seconds to settle..."
	@sleep ${SERVER_STOP_ALLOWANCE}

.PHONY: test gild run_test run_gild report start_webserver kill_webserver clean

