#!/bin/bash

echo "Starting backend server..."
cd /Users/arda/Desktop/novamind/novamind/backend
/Users/arda/Desktop/novamind/novamind/backend/venv/bin/uvicorn main:app --reload &
B_PID=$!
echo "Backend server started with PID $B_PID"

echo "Starting frontend server..."
cd /Users/arda/Desktop/novamind/novamind/frontend
npm run dev &
F_PID=$!
echo "Frontend server started with PID $F_PID"

echo "To stop the servers, run:"
echo "kill $B_PID"
echo "kill $F_PID"
