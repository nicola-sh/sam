#!/usr/bin/env bash
# =============================================================================
# rrn_trace_id.sh — поиск RRN в логах и сбор связок trace_id1 + trace_id2
#
# Под одним RRN может быть несколько пар (trace_id1, trace_id2).
# Формат в логе: [имя_сервиса, trace_id1, trace_id2]
#   пример: [switch-service, 7a1b..., 9c2d...]
#
# Использование:
#   ./rrn_trace_id.sh RRN [YYYY-MM-DD] [PART]
#   ./rrn_trace_id.sh 611947394858 2026-04-29
#   ./rrn_trace_id.sh 611947394858 2026-04-29 01
#   ./rrn_trace_id.sh 611947394858 2026-04-29 01,02,03
#
# PART — суффикс файла вместо * в имени архива:
#   * или пусто  → switch-service.2026-04-29_*.gz  (все части)
#   01           → switch-service.2026-04-29_01.gz (один файл)
#   01,02        → несколько конкретных частей
#
# Переменные окружения (опционально):
#   LOG_ROOT          — корень логов (по умолчанию /srv_mproc/mproc/services)
#   TARGET_DIR        — куда писать результат (по умолчанию $HOME/logs)
#   LOG_PART          — то же, что аргумент PART (если PART не задан)
#   SCAN_MODE         — fast (по умолчанию) или full
#   CONTEXT_BEFORE    — строк до RRN в fast-режиме (по умолчанию 80)
#   CONTEXT_AFTER     — строк после RRN в fast-режиме (по умолчанию 40)
#
# Результат:
#   $TARGET_DIR/final_composite_log_RRN_<RRN>.txt
#   $TARGET_DIR/tmp_<RRN>/ — промежуточные файлы
# =============================================================================

set -euo pipefail

RRN="${1:-}"
DATE="${2:-}"
LOG_PART_ARG="${3:-}"

if [[ -z "$RRN" ]]; then
  echo "Использование: $0 RRN [YYYY-MM-DD] [PART]" >&2
  echo "  PART: * | 01 | 01,02,03  (суффикс вместо _* в имени лога)" >&2
  exit 1
fi

if [[ -z "$DATE" ]]; then
  DATE="$(date +%F)"
fi

LOG_ROOT="${LOG_ROOT:-/srv_mproc/mproc/services}"
TARGET_DIR="${TARGET_DIR:-$HOME/logs}"
LOG_PART="${LOG_PART_ARG:-${LOG_PART:-*}}"
TMP_DIR="${TARGET_DIR}/tmp_${RRN}"
PAIRS_FILE="${TMP_DIR}/trace_pairs.tsv"
FINAL_LOG="${TARGET_DIR}/final_composite_log_RRN_${RRN}.txt"
SCAN_MODE="${SCAN_MODE:-fast}"
CONTEXT_BEFORE="${CONTEXT_BEFORE:-80}"
CONTEXT_AFTER="${CONTEXT_AFTER:-40}"

# Пути к архивам логов (PART подставляется вместо * в _PART.gz / _PART.log)
SEARCH_PATTERNS=()

add_patterns_for_suffix() {
  local suffix="$1"
  SEARCH_PATTERNS+=(
    "${LOG_ROOT}/switch-service/log_arch/switch-service.${DATE}_${suffix}.gz"
    "${LOG_ROOT}/swith-service/log_arch/switch-service.${DATE}_${suffix}.gz"
    "${LOG_ROOT}/stip-service/log_arch/stip-service.${DATE}_${suffix}.gz"
    "${LOG_ROOT}/switch-service/log/switch-service.${DATE}_${suffix}.log"
    "${LOG_ROOT}/switch-service/log_arch/switch-service.${DATE}_${suffix}.log"
    "${LOG_ROOT}/stip-service/log/stip-service.${DATE}_${suffix}.log"
    "${LOG_ROOT}/stip-service/log_arch/stip-service.${DATE}_${suffix}.log"
  )
}

if [[ -z "$LOG_PART" || "$LOG_PART" == "*" ]]; then
  add_patterns_for_suffix "*"
else
  IFS=',' read -ra LOG_PARTS <<<"$LOG_PART"
  for part in "${LOG_PARTS[@]}"; do
    part="${part//[[:space:]]/}"
    [[ -n "$part" ]] || continue
    add_patterns_for_suffix "$part"
  done
fi

mkdir -p "$TARGET_DIR" "$TMP_DIR"
rm -f "$PAIRS_FILE"
: >"$PAIRS_FILE"

file_contains_rrn() {
  local f="$1"
  if [[ "$f" == *.gz ]]; then
    zgrep -q -F -- "$RRN" "$f" 2>/dev/null
  else
    grep -q -F -- "$RRN" "$f" 2>/dev/null
  fi
}

grep_rrn_context() {
  local f="$1"
  if [[ "$f" == *.gz ]]; then
    zgrep -F -B "$CONTEXT_BEFORE" -A "$CONTEXT_AFTER" -- "$RRN" "$f" 2>/dev/null || true
  else
    grep -F -B "$CONTEXT_BEFORE" -A "$CONTEXT_AFTER" -- "$RRN" "$f" 2>/dev/null || true
  fi
}

# -----------------------------------------------------------------------------
# Раскрыть glob-паттерны в список существующих файлов
# -----------------------------------------------------------------------------
VALID_FILES=()
for pattern in "${SEARCH_PATTERNS[@]}"; do
  # shellcheck disable=SC2086
  for f in $pattern; do
    [[ -f "$f" ]] && VALID_FILES+=("$f")
  done
done

if ((${#VALID_FILES[@]} == 0)); then
  echo "Файлы логов не найдены для даты ${DATE}." >&2
  echo "Проверьте LOG_ROOT=${LOG_ROOT} и дату." >&2
  exit 1
fi

echo "RRN: ${RRN}"
echo "Дата: ${DATE}"
echo "Часть лога (PART): ${LOG_PART}"
echo "Файлов: ${#VALID_FILES[@]}"
echo "Режим фазы 1: ${SCAN_MODE}"
echo "TMP: ${TMP_DIR}"

# -----------------------------------------------------------------------------
# Фаза 1: найти все уникальные пары trace_id1 / trace_id2 по RRN
# Формат в логе: [service, trace_id1, trace_id2]
# Блоки логов разделяются строкой ---E--- (если нет — по пустой строке)
# -----------------------------------------------------------------------------
extract_pairs_awk='
function trim(s) {
  gsub(/^[ \t\r\n]+|[ \t\r\n]+$/, "", s)
  return s
}
function register_pair(svc, t1, t2,   key) {
  if (t1 == "" || t2 == "") return
  key = t1 "|||" t2
  if (!(key in seen)) {
    seen[key] = 1
    print t1 "\t" t2 "\t" svc >> pairs_file
  }
}
function extract_trace_pairs(b,   rest, s, n, i, svc, t1, t2, parts) {
  # Все вхождения [service, id1, id2] в блоке (mawk/gawk)
  rest = b
  while (match(rest, /\[[^]\n]+\]/)) {
    s = substr(rest, RSTART + 1, RLENGTH - 2)
    rest = substr(rest, RSTART + RLENGTH)
    n = split(s, parts, ",")
    if (n >= 3) {
      svc = trim(parts[1])
      t1 = trim(parts[2])
      t2 = trim(parts[3])
      register_pair(svc, t1, t2)
    }
  }
}
function flush_block(b) {
  if (b == "") return
  if (b !~ rrn) return
  extract_trace_pairs(b)
}
BEGIN {
  rrn = ENVIRON["RRN_VAL"]
  pairs_file = ENVIRON["PAIRS_FILE"]
  b = ""
  RS = "\n"
}
{
  line = $0
  if (line ~ /^---E---[[:space:]]*$/) {
    flush_block(b)
    b = ""
    next
  }
  if (line ~ /^[[:space:]]*$/ && b != "") {
    flush_block(b)
    b = ""
    next
  }
  if (b == "") b = line
  else b = b "\n" line
}
END {
  flush_block(b)
}
'

extract_pairs_fast_awk='
function trim(s) {
  gsub(/^[ \t\r\n]+|[ \t\r\n]+$/, "", s)
  return s
}
function register_pair(svc, t1, t2,   key) {
  if (t1 == "" || t2 == "") return
  key = t1 "|||" t2
  if (!(key in seen)) {
    seen[key] = 1
    print t1 "\t" t2 "\t" svc >> pairs_file
  }
}
function extract_trace_pairs(b,   rest, s, n, svc, t1, t2, parts) {
  rest = b
  while (match(rest, /\[[^]\n]+\]/)) {
    s = substr(rest, RSTART + 1, RLENGTH - 2)
    rest = substr(rest, RSTART + RLENGTH)
    n = split(s, parts, ",")
    if (n >= 3) {
      svc = trim(parts[1])
      t1 = trim(parts[2])
      t2 = trim(parts[3])
      register_pair(svc, t1, t2)
    }
  }
}
function process_chunk(chunk) {
  if (chunk == "" || chunk !~ rrn) return
  extract_trace_pairs(chunk)
}
BEGIN {
  rrn = ENVIRON["RRN_VAL"]
  pairs_file = ENVIRON["PAIRS_FILE"]
  chunk = ""
}
{
  if ($0 == "--") {
    process_chunk(chunk)
    chunk = ""
    next
  }
  chunk = (chunk == "" ? $0 : chunk "\n" $0)
}
END {
  process_chunk(chunk)
}
'

for f in "${VALID_FILES[@]}"; do
  base="$(basename "$f")"
  if ! file_contains_rrn "$f"; then
    echo "  [1/3] пропуск (нет RRN): ${base}"
    continue
  fi

  echo "  [1/3] пары trace: ${base}"
  export RRN_VAL="$RRN" PAIRS_FILE="$PAIRS_FILE"

  if [[ "$SCAN_MODE" == "full" ]]; then
    if [[ "$f" == *.gz ]]; then
      zcat -- "$f" | awk "$extract_pairs_awk"
    else
      awk "$extract_pairs_awk" "$f"
    fi
  else
    grep_rrn_context "$f" | awk "$extract_pairs_fast_awk"
  fi
done

# Уникальные пары
if [[ -s "$PAIRS_FILE" ]]; then
  sort -u "$PAIRS_FILE" -o "$PAIRS_FILE"
fi

PAIR_COUNT=0
if [[ -s "$PAIRS_FILE" ]]; then
  PAIR_COUNT=$(wc -l <"$PAIRS_FILE" | tr -d " ")
fi

echo "Найдено связок trace_id1/trace_id2: ${PAIR_COUNT}"

if [[ "$PAIR_COUNT" -eq 0 ]]; then
  echo "RRN ${RRN} не найден (нет пар trace_id в логах)." >&2
  rm -rf "$TMP_DIR"
  exit 2
fi

echo "Связки (service | trace_id1 -> trace_id2):"
while IFS=$'\t' read -r t1 t2 svc; do
  echo "  [${svc}]  ${t1}  |  ${t2}"
done <"$PAIRS_FILE"

# -----------------------------------------------------------------------------
# Фаза 2: по каждой паре собрать блоки ARR1 (оба trace) и ARR2 (только trace_2)
# -----------------------------------------------------------------------------
collect_blocks_awk='
function trim(s) {
  gsub(/^[ \t\r\n]+|[ \t\r\n]+$/, "", s)
  return s
}
function flush_block(b,   has_t1, has_t2) {
  if (b == "") return
  has_t1 = (index(b, t1) > 0)
  has_t2 = (index(b, t2) > 0)
  if (has_t1 && has_t2) {
    print "ARR1\t" fname "\n" b "\n---E---\n" >> out_file
  } else if (has_t2) {
    print "ARR2\t" fname "\n" b "\n---E---\n" >> out_file
  }
}
BEGIN {
  t1 = ENVIRON["T1"]
  t2 = ENVIRON["T2"]
  fname = ENVIRON["FNAME"]
  out_file = ENVIRON["OUT_TMP"]
  b = ""
}
{
  line = $0
  if (line ~ /^---E---[[:space:]]*$/) {
    flush_block(b)
    b = ""
    next
  }
  if (line ~ /^[[:space:]]*$/ && b != "") {
    flush_block(b)
    b = ""
    next
  }
  if (b == "") b = line
  else b = b "\n" line
}
END { flush_block(b) }
'

pair_idx=0
while IFS=$'\t' read -r TRACE_1 TRACE_2 SERVICE_NAME; do
  pair_idx=$((pair_idx + 1))
  OUT_TMP="${TMP_DIR}/pair_${pair_idx}.tmp"
  : >"$OUT_TMP"
  echo "  [2/3] пара #${pair_idx} [${SERVICE_NAME}]: ${TRACE_1} | ${TRACE_2}"

  for f in "${VALID_FILES[@]}"; do
    export T1="$TRACE_1" T2="$TRACE_2" FNAME="$f" OUT_TMP="$OUT_TMP"
    if [[ "$f" == *.gz ]]; then
      zcat -- "$f" | awk "$collect_blocks_awk"
    else
      awk "$collect_blocks_awk" "$f"
    fi
  done
done <"$PAIRS_FILE"

TMP_COUNT=$(find "$TMP_DIR" -maxdepth 1 -name 'pair_*.tmp' -size +0c 2>/dev/null | wc -l | tr -d ' ')
if [[ "$TMP_COUNT" -eq 0 ]]; then
  echo "RRN ${RRN}: пары найдены, но блоки по trace_id в логах не собраны." >&2
  exit 3
fi

# -----------------------------------------------------------------------------
# Фаза 3: сводный отчёт (как на вашем скрине: ARR1 / ARR2)
# -----------------------------------------------------------------------------
{
  echo "=== СВОДНЫЙ ЛОГ RRN: ${RRN} ==="
  echo "Дата логов: ${DATE}"
  echo "Связок trace: ${PAIR_COUNT}"
  echo ""
} >"$FINAL_LOG"

pair_idx=0
while IFS=$'\t' read -r TRACE_1 TRACE_2 SERVICE_NAME; do
  pair_idx=$((pair_idx + 1))
  OUT_TMP="${TMP_DIR}/pair_${pair_idx}.tmp"
  [[ -s "$OUT_TMP" ]] || continue

  {
    echo ""
    echo "################################################################"
    echo "### ПАРА #${pair_idx} [${SERVICE_NAME}]: TRACE_1=${TRACE_1}  TRACE_2=${TRACE_2}"
    echo "################################################################"
  } >>"$FINAL_LOG"

  for MODE in ARR1 ARR2; do
    if [[ "$MODE" == "ARR1" ]]; then
      H="ПЕРЕСЕЧЕНИЕ (TRACE_1 И TRACE_2 ВМЕСТЕ)"
    else
      H="СКВОЗНАЯ ЦЕПОЧКА (ТОЛЬКО TRACE_2)"
    fi

    {
      echo ""
      echo "--- ${H} ---"
      echo ""
    } >>"$FINAL_LOG"

    awk -v target="$MODE" '
      BEGIN { RS = "\n---E---\n" }
      NF == 0 { next }
      {
        nl = index($0, "\n")
        if (nl == 0) next
        header = substr($0, 1, nl - 1)
        body = substr($0, nl + 1)
        tab = index(header, "\t")
        if (tab == 0) next
        tg = substr(header, 1, tab - 1)
        fn = substr(header, tab + 1)
        if (tg != target) next
        print "----------------------------------------"
        print "[ИЗ ФАЙЛА: " fn "]"
        print body
        print ""
      }
    ' "$OUT_TMP" >>"$FINAL_LOG"
  done
done <"$PAIRS_FILE"

echo "  [3/3] готово"
echo "Успех! Файл сохранён: ${FINAL_LOG}"
echo "Промежуточные файлы: ${TMP_DIR}"
