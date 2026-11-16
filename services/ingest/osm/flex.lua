-- Import OpenStreetMap → PostGIS per Cordata (osm2pgsql ≥ 1.7, output "flex").
--
-- Uso (vedi services/ingest/README.md):
--   osm2pgsql -O flex -S services/ingest/osm/flex.lua -d cordata data/osm/pilot.osm.pbf
--
-- Tabelle prodotte (tutte in WGS84, EPSG:4326):
--   osm_routes         relazioni route=hiking/foot con i tag escursionistici e la geometria
--   osm_route_members  way che compongono ciascuna relazione, in ordine
--   osm_ways           way percorribili a piedi con sac_scale, trail_visibility, ecc.
--   osm_pois           punti di interesse per l'escursionismo (rifugi, cime, laghi, acqua…)

local function number_or_nil(value)
    if not value then return nil end
    -- "2253", "2253 m", "2.253,5" → numero; i separatori delle migliaia sono rari ma esistono
    local cleaned = value:gsub("%s*m%s*$", ""):gsub(",", ".")
    local n = tonumber(cleaned:match("^%s*(-?%d+%.?%d*)"))
    return n
end

local function duration_minutes(value)
    -- duration:forward è in genere "hh:mm" (a volte "h:mm" o minuti)
    if not value then return nil end
    local h, m = value:match("^%s*(%d+):(%d%d)")
    if h then return tonumber(h) * 60 + tonumber(m) end
    return number_or_nil(value)
end

local tables = {}

tables.routes = osm2pgsql.define_relation_table('osm_routes', {
    { column = 'route', type = 'text' },
    { column = 'ref', type = 'text' },
    { column = 'reg_ref', type = 'text' },
    { column = 'ref_rei', type = 'text' },
    { column = 'name', type = 'text' },
    { column = 'name_it', type = 'text' },
    { column = 'name_de', type = 'text' },
    { column = 'network', type = 'text' },
    { column = 'operator', type = 'text' },
    { column = 'cai_scale', type = 'text' },
    { column = 'osmc_symbol', type = 'text' },
    { column = 'from_place', type = 'text' },
    { column = 'to_place', type = 'text' },
    { column = 'roundtrip', type = 'text' },
    { column = 'ascent_m', type = 'real' },
    { column = 'descent_m', type = 'real' },
    { column = 'duration_forward_min', type = 'int' },
    { column = 'duration_backward_min', type = 'int' },
    { column = 'source', type = 'text' },
    { column = 'tags', type = 'jsonb' },
    { column = 'geom', type = 'multilinestring', projection = 4326 },
})

tables.route_members = osm2pgsql.define_table({
    name = 'osm_route_members',
    ids = { type = 'relation', id_column = 'relation_id' },
    columns = {
        { column = 'seq', type = 'int', not_null = true },
        { column = 'way_id', type = 'int8', not_null = true },
        { column = 'role', type = 'text' },
    },
})

tables.ways = osm2pgsql.define_way_table('osm_ways', {
    { column = 'highway', type = 'text', not_null = true },
    { column = 'name', type = 'text' },
    { column = 'sac_scale', type = 'text' },
    { column = 'trail_visibility', type = 'text' },
    { column = 'tracktype', type = 'text' },
    { column = 'surface', type = 'text' },
    { column = 'access', type = 'text' },
    { column = 'foot', type = 'text' },
    { column = 'bridge', type = 'bool' },
    { column = 'tunnel', type = 'bool' },
    { column = 'tags', type = 'jsonb' },
    { column = 'geom', type = 'linestring', projection = 4326, not_null = true },
})

tables.pois = osm2pgsql.define_table({
    name = 'osm_pois',
    ids = { type = 'any', id_column = 'osm_id', type_column = 'osm_type' },
    columns = {
        { column = 'kind', type = 'text', not_null = true },
        { column = 'name', type = 'text' },
        { column = 'name_it', type = 'text' },
        { column = 'name_de', type = 'text' },
        { column = 'ele', type = 'real' },
        { column = 'tags', type = 'jsonb' },
        { column = 'geom', type = 'point', projection = 4326, not_null = true },
    },
})

-- highway percorribili a piedi (le strade principali servono solo come collegamento)
local walkable = {
    path = true, footway = true, track = true, steps = true, bridleway = true,
    pedestrian = true, living_street = true, residential = true, service = true,
    unclassified = true, tertiary = true, secondary = true, primary = true, via_ferrata = true,
}

-- tipo di POI a partire dai tag; nil se l'oggetto non interessa
local function poi_kind(tags)
    if tags.tourism == 'alpine_hut' then return 'rifugio' end
    if tags.tourism == 'wilderness_hut' then return 'bivacco' end
    if tags.amenity == 'shelter' then return 'riparo' end
    if tags.natural == 'peak' then return 'cima' end
    if tags.natural == 'saddle' or tags.mountain_pass == 'yes' then return 'sella' end
    if tags.natural == 'spring' then return 'sorgente' end
    if tags.amenity == 'drinking_water' then return 'acqua_potabile' end
    if tags.amenity == 'parking' then return 'parcheggio' end
    if tags.tourism == 'viewpoint' then return 'panorama' end
    if tags.waterway == 'waterfall' then return 'cascata' end
    if tags.tourism == 'information' and tags.information == 'guidepost' then return 'palina' end
    if tags.natural == 'water' and tags.name
        and (tags.water == nil or tags.water == 'lake' or tags.water == 'pond' or tags.water == 'reservoir') then
        return 'lago'
    end
    local place = tags.place
    if place == 'village' or place == 'hamlet' or place == 'isolated_dwelling'
        or place == 'locality' or place == 'town' or place == 'city' then
        return 'localita'
    end
    return nil
end

local function insert_poi(object, kind, geom)
    local tags = object.tags
    tables.pois:insert({
        kind = kind,
        name = tags.name,
        name_it = tags['name:it'],
        name_de = tags['name:de'],
        ele = number_or_nil(tags.ele),
        tags = tags,
        geom = geom,
    })
end

function osm2pgsql.process_node(object)
    local kind = poi_kind(object.tags)
    if kind then insert_poi(object, kind, object:as_point()) end
end

function osm2pgsql.process_way(object)
    local tags = object.tags
    local hw = tags.highway
    if hw and walkable[hw] and tags.area ~= 'yes' then
        tables.ways:insert({
            highway = hw,
            name = tags.name,
            sac_scale = tags.sac_scale,
            trail_visibility = tags.trail_visibility,
            tracktype = tags.tracktype,
            surface = tags.surface,
            access = tags.access,
            foot = tags.foot,
            bridge = tags.bridge ~= nil and tags.bridge ~= 'no',
            tunnel = tags.tunnel ~= nil and tags.tunnel ~= 'no',
            tags = tags,
            geom = object:as_linestring(),
        })
    end
    local kind = poi_kind(tags)
    if kind and object.is_closed then
        insert_poi(object, kind, object:as_polygon():centroid())
    elseif kind then
        insert_poi(object, kind, object:as_linestring():centroid())
    end
end

function osm2pgsql.process_relation(object)
    local tags = object.tags
    if tags.type == 'route' and (tags.route == 'hiking' or tags.route == 'foot') then
        tables.routes:insert({
            route = tags.route,
            ref = tags.ref,
            reg_ref = tags.reg_ref,
            ref_rei = tags['ref:REI'],
            name = tags.name,
            name_it = tags['name:it'],
            name_de = tags['name:de'],
            network = tags.network,
            operator = tags.operator,
            cai_scale = tags.cai_scale,
            osmc_symbol = tags['osmc:symbol'],
            from_place = tags.from,
            to_place = tags.to,
            roundtrip = tags.roundtrip,
            ascent_m = number_or_nil(tags.ascent),
            descent_m = number_or_nil(tags.descent),
            duration_forward_min = duration_minutes(tags['duration:forward']),
            duration_backward_min = duration_minutes(tags['duration:backward']),
            source = tags.source,
            tags = tags,
            geom = object:as_multilinestring(),
        })
        local seq = 0
        for _, member in ipairs(object.members) do
            if member.type == 'w' then
                seq = seq + 1
                tables.route_members:insert({ seq = seq, way_id = member.ref, role = member.role })
            end
        end
        return
    end
    if tags.type == 'multipolygon' then
        local kind = poi_kind(tags)
        if kind then insert_poi(object, kind, object:as_multipolygon():centroid()) end
    end
end
