#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"
REQUIRED_VARS=(
  DATABASE_URL
  TELEGRAM_API_ID
  TELEGRAM_API_HASH
  OPENAI_API_KEY
)

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

unquote() {
  local value="$1"
  if [[ ${#value} -ge 2 ]]; then
    if [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
      value="${value:1:${#value}-2}"
    fi
  fi
  printf '%s' "$value"
}

get_env_value() {
  local key="$1"
  local line name value

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim "$line")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue

    if [[ "$line" == export[[:space:]]* ]]; then
      line="$(trim "${line#export}")"
    fi

    [[ "$line" == *=* ]] || continue
    name="$(trim "${line%%=*}")"
    [[ "$name" == "$key" ]] || continue

    value="$(trim "${line#*=}")"
    unquote "$value"
    return 0
  done < "$ENV_FILE"

  return 1
}

is_invalid_placeholder() {
  local key="$1"
  local value="$2"

  [[ -z "$value" ]] && return 0
  [[ "$value" == "CHANGE_ME" ]] && return 0
  [[ "$value" == "..." ]] && return 0
  [[ "$value" == *"USER:PASSWORD"* ]] && return 0
  [[ "$value" == *"DB_NAME"* ]] && return 0
  [[ "$key" == "OPENAI_API_KEY" && "$value" == *"sk-..."* ]] && return 0

  return 1
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Invalid environment config: $ENV_FILE does not exist." >&2
  exit 1
fi

invalid_vars=()

for key in "${REQUIRED_VARS[@]}"; do
  if ! value="$(get_env_value "$key")"; then
    invalid_vars+=("$key missing")
    continue
  fi

  if is_invalid_placeholder "$key" "$value"; then
    invalid_vars+=("$key invalid or placeholder")
  fi
done

if (( ${#invalid_vars[@]} > 0 )); then
  echo "Invalid environment config in $ENV_FILE:" >&2
  for item in "${invalid_vars[@]}"; do
    echo "- $item" >&2
  done
  echo "Update $ENV_FILE with production values before deploying." >&2
  exit 1
fi

echo "Environment config validation passed."
