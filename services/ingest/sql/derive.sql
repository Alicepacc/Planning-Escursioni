-- Tabelle derivate per mappa e schede (eseguito da `python -m cordata_ingest.build derive`).
-- Prerequisiti: import osm2pgsql (osm_routes, osm_route_members, osm_ways, osm_pois) e
-- tabella osm2cai_routes caricata da `build load-osm2cai`.

-- 1. Sentieri: relazioni OSM arricchite con i dati ufficiali OSM2CAI (aggancio su relation_id)
DROP TABLE IF EXISTS trails;
CREATE TABLE trails AS
SELECT
    r.relation_id,
    c.id AS osm2cai_id,
    COALESCE(NULLIF(r.ref, ''), c.ref) AS ref,
    r.reg_ref,
    COALESCE(r.name_it, r.name, c.name) AS name,
    r.name_de,
    r.network,
    r.operator,
    COALESCE(c.cai_scale, r.cai_scale) AS cai_scale,
    r.osmc_symbol,
    COALESCE(c.from_place, r.from_place) AS from_place,
    COALESCE(c.to_place, r.to_place) AS to_place,
    c.sda,
    c.distance_km AS official_distance_km,
    c.ascent_m AS official_ascent_m,
    c.descent_m AS official_descent_m,
    c.duration_forward_min AS official_duration_forward_min,
    c.duration_backward_min AS official_duration_backward_min,
    c.issues_status,
    c.issues_description,
    c.issues_last_update,
    c.validation_date,
    c.public_page,
    COALESCE(c.geom, r.geom) AS geom
FROM osm_routes r
LEFT JOIN osm2cai_routes c ON c.relation_id = r.relation_id
WHERE r.geom IS NOT NULL;
CREATE INDEX ON trails USING gist (geom);
CREATE INDEX ON trails (relation_id);
CREATE INDEX ON trails (osm2cai_id);

-- 2. Tratti di sentiero per la mappa: ogni way che appartiene ad almeno una relazione, con i
--    numeri di tutti i sentieri che la percorrono (niente linee sovrapposte sulla mappa).
DROP TABLE IF EXISTS trail_ways;
CREATE TABLE trail_ways AS
WITH membership AS (
    SELECT DISTINCT m.way_id, t.relation_id, t.osm2cai_id, t.ref, t.cai_scale, t.network,
           t.osmc_symbol, t.sda
    FROM osm_route_members m
    JOIN trails t ON t.relation_id = m.relation_id
)
SELECT
    w.way_id,
    w.highway,
    w.sac_scale,
    w.trail_visibility,
    string_agg(DISTINCT NULLIF(mb.ref, ''), ' · ' ORDER BY NULLIF(mb.ref, '')) AS refs,
    array_agg(DISTINCT mb.relation_id) AS relation_ids,
    array_remove(array_agg(DISTINCT mb.osm2cai_id), NULL) AS osm2cai_ids,
    array_remove(array_agg(DISTINCT mb.cai_scale), NULL) AS cai_scales,
    -- rete più importante: internazionale > nazionale > regionale > locale
    min(CASE mb.network WHEN 'iwn' THEN 1 WHEN 'nwn' THEN 2 WHEN 'rwn' THEN 3 ELSE 4 END) AS network_rank,
    max(COALESCE(mb.sda, -1)) AS sda,
    (array_agg(mb.osmc_symbol ORDER BY mb.osmc_symbol) FILTER (WHERE mb.osmc_symbol IS NOT NULL))[1] AS osmc_symbol,
    w.geom
FROM membership mb
JOIN osm_ways w ON w.way_id = mb.way_id
GROUP BY w.way_id, w.highway, w.sac_scale, w.trail_visibility, w.geom;
CREATE INDEX ON trail_ways USING gist (geom);
