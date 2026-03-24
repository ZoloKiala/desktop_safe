from pathlib import Path

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_PRIMARY_EXTS = (
    ".csv",
    ".xlsx",
    ".xls",
    ".shp",
    ".geojson",
    ".json",
    ".gpkg",
)

LAT_CANDIDATES = ("latitude", "lat", "y")
LON_CANDIDATES = ("longitude", "lon", "long", "lng", "x")
DATE_CANDIDATES = ("date", "sampling_date", "sample_date", "observation_date")
ID_CANDIDATES = ("id", "_id", "plotid", "plot_id", "sensor_id", "station_id")
DESCRIPTION_CANDIDATES = ("description", "desc", "notes", "comment", "remarks")

PARAMETERS_SQL = """
select
    p."Id" as "ParameterId",
    p."Name" as "ParameterName",
    pu."Id" as "UnitId",
    pu."Unit" as "Unit",
    pu."Name" as "UnitName"
from public."Parameters" p
join public."ParameterUnits" pu
    on pu."ParameterId" = p."Id"
order by p."Id"
"""

SERIES_SQL = """
select
    s."Id" as "SeriesId",
    s."UnitsId",
    p."Name",
    t."Id" as "TopologyId",
    t."Key",
    s."DatasetId",
    s."DatasetName"
from public."Series" s
join public."Topologies" t
    on t."Id" = s."TopologyId"
join public."ParameterUnits" pu
    on pu."Id" = s."UnitsId"
join public."Parameters" p
    on p."Id" = pu."ParameterId"
order by s."Id"
"""