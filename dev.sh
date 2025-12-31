#!/bin/bash
# Development helper script for Libertas

PORT=${PORT:-5555}

case "$1" in
  start)
    # Kill any existing server on the port
    lsof -ti:$PORT | xargs kill 2>/dev/null
    sleep 1
    echo "Starting server on port $PORT..."
    python3 server.py
    ;;

  bg)
    # Start in background with logs
    lsof -ti:$PORT | xargs kill 2>/dev/null
    sleep 1
    echo "Starting server in background on port $PORT..."
    python3 server.py > /tmp/libertas.log 2>&1 &
    echo "PID: $!"
    echo "Logs: tail -f /tmp/libertas.log"
    ;;

  stop)
    echo "Stopping server..."
    lsof -ti:$PORT | xargs kill 2>/dev/null
    pkill -f "python3 server.py" 2>/dev/null
    echo "Stopped"
    ;;

  logs)
    tail -f /tmp/libertas.log
    ;;

  test)
    echo "Running flight parsing tests..."
    python3 tests/test_flight_parsing.py
    ;;

  *)
    echo "Usage: ./dev.sh {start|bg|stop|logs|test}"
    echo ""
    echo "  start  - Start server in foreground"
    echo "  bg     - Start server in background"
    echo "  stop   - Stop the server"
    echo "  logs   - Tail the log file"
    echo "  test   - Run tests"
    ;;
esac
