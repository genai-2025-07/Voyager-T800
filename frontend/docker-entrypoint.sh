#!/bin/sh
set -e

HTML=/usr/share/nginx/html/index.html

# Inject API_BASE_URL into the runtime env placeholder in index.html
# Expecting index.html to contain: window.__ENV = { API_BASE_URL: "" };
if [ -n "$API_BASE_URL" ] && [ -f "$HTML" ]; then
  # Escape chars for sed
  esc=$(printf '%s' "$API_BASE_URL" | sed -e 's/[\/&]/\\&/g')
  sed -i "s|window.__ENV = { API_BASE_URL: \"\" }|window.__ENV = { API_BASE_URL: \"$esc\" }|g" "$HTML" || true
fi