#!/bin/sh
port=":5000"
if [ "$1" ];
then
	port=$1
fi

netstat -an | grep "$port" | grep "ESTABLISHED" | wc -l
