#!/bin/bash

TWILIO_API_KEY="cb7twilio"
URL="https://internal.mcb7.org/incomingtext?auth=${TWILIO_API_KEY}&cb=7"

NUMBERS_FILE="${1:-test_numbers.txt}"

if [[ ! -f "$NUMBERS_FILE" ]]; then
  echo "Error: numbers file '$NUMBERS_FILE' not found."
  echo "Create it with one phone number per line (e.g. +12125551234)"
  exit 1
fi

NUMBERS=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -n "$line" ]] && NUMBERS+=("$line")
done < "$NUMBERS_FILE"

VOTES=("yes" "yes" "yes" "no" "yes" "abstain" "yes" "no" "yes" "yes" "yes" "cause" "yes" "no" "yes" "yes" "abstain" "yes" "no" "yes")

echo "Sending ${#NUMBERS[@]} votes concurrently..."

for i in "${!NUMBERS[@]}"; do
  NUMBER="${NUMBERS[$i]}"
  VOTE="${VOTES[$((i % ${#VOTES[@]}))]}"

  # Twilio posts an application/x-www-form-urlencoded body; apig-wsgi hands
  # that straight to Flask as text, so just send a normal form POST.
  curl -s -o /dev/null -w "${NUMBER} (${VOTE}): %{http_code}\n" \
    -X POST "$URL" \
    --data-urlencode "Body=${VOTE}" \
    --data-urlencode "From=${NUMBER}" &
done

wait
echo "Done."
