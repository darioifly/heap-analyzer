import proj4 from "proj4";
import { register } from "ol/proj/proj4";
import { get as getProjection } from "ol/proj";
import type { Projection } from "ol/proj";

proj4.defs(
  "EPSG:32632",
  "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs +type=crs",
);
proj4.defs(
  "EPSG:32633",
  "+proj=utm +zone=33 +datum=WGS84 +units=m +no_defs +type=crs",
);
register(proj4);

export function getUtmProjection(crs: string): Projection {
  const proj = getProjection(crs);
  if (!proj) throw new Error(`Projection ${crs} not registered`);
  return proj;
}
