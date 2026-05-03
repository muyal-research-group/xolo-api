#!/bin/bash
readonly API_TOKEN=$1
readonly account_id=$2
readonly to_email=$3
readonly from_email="support@mictlanx.com"

curl "https://api.cloudflare.com/client/v4/accounts/$account_id/email/sending/send" \
  --header "Authorization: Bearer $API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "to": "'"$to_email"'",
    "from": "'"$from_email"'",
    "subject": "Welcome to our service!",
    "html": "<h1>Welcome!</h1><p>Thanks for signing up.</p>",
    "text": "Welcome! Thanks for signing up."
  }'