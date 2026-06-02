-- =============================================================================
-- Сверка заблокированных средств: proc_stip.account vs proc_stip.event
-- =============================================================================
-- Назначение: найти счета, где locked_amount не совпадает с суммой LOCKED-событий.
-- BIN-фильтр убран (в старом скрипте OR-логика часто не фильтровала include).
--
-- Параметры (менять в CTE params):
--   since_ts   — нижняя граница e.request_time
--   tolerance  — игнорировать |diff| <= tolerance (например 0.01)
--
-- Запуск: psql / DBeaver / любой PG-клиент на схеме proc_stip
-- =============================================================================

WITH params AS (
  SELECT
    timestamptz '2026-05-01 00:00:01+03' AS since_ts,
    0::numeric AS tolerance
),
ev AS (
  SELECT
    e.account_id,
    e.currency_id,
    sum(
      CASE rm.locking_sign
        WHEN 'C' THEN -e.account_amount
        WHEN 'D' THEN  e.account_amount
        WHEN '0' THEN  e.account_amount
      END
    ) AS event_sum,
    count(*) FILTER (WHERE rm.locking_sign IS NULL) AS no_metadata_cnt
  FROM proc_stip.event e
  LEFT JOIN proc_stip.request_metadata rm
    ON rm.mti = left(e.mti, 3)
   AND rm.proc_code = left(e.proc_code, 2)
  CROSS JOIN params p
  WHERE e.lock_status = 'LOCKED'
    AND e.account_id IS NOT NULL
    AND e.request_time >= p.since_ts
  GROUP BY e.account_id, e.currency_id
)
SELECT
  a.account_id,
  a.currency_id,
  a.locked_amount,
  coalesce(ev.event_sum, 0) AS locked_amount_sum,
  a.locked_amount - coalesce(ev.event_sum, 0) AS diff,
  coalesce(ev.no_metadata_cnt, 0) AS events_without_metadata
FROM proc_stip.account a
LEFT JOIN ev USING (account_id, currency_id)
CROSS JOIN params p
WHERE abs(a.locked_amount - coalesce(ev.event_sum, 0)) > p.tolerance
   OR coalesce(ev.no_metadata_cnt, 0) > 0
ORDER BY abs(a.locked_amount - coalesce(ev.event_sum, 0)) DESC;


-- =============================================================================
-- Детализация по одному счёту (раскомментировать, подставить id)
-- =============================================================================
/*
WITH params AS (
  SELECT timestamptz '2026-05-01 00:00:01+03' AS since_ts
)
SELECT
  e.event_id,
  e.request_time,
  e.bin_id,
  e.mti,
  e.proc_code,
  e.account_amount,
  rm.locking_sign,
  CASE rm.locking_sign
    WHEN 'C' THEN -e.account_amount
    WHEN 'D' THEN  e.account_amount
    WHEN '0' THEN  e.account_amount
  END AS signed_amount
FROM proc_stip.event e
LEFT JOIN proc_stip.request_metadata rm
  ON rm.mti = left(e.mti, 3)
 AND rm.proc_code = left(e.proc_code, 2)
CROSS JOIN params p
WHERE e.account_id = 123456
  AND e.currency_id = 643
  AND e.lock_status = 'LOCKED'
  AND e.request_time >= p.since_ts
ORDER BY e.request_time;
*/
