// Esportazione della traccia (SPEC §5.2 «Esporta GPX/KML»): file generati nel browser dai
// punti del profilo (lon, lat, quota), senza server.

/** [lon, lat, quota] */
export type TrackPoint = [number, number, number];

function esc(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

export interface Waypoint {
	name: string;
	lon: number;
	lat: number;
	ele?: number | null;
}

export function toGpx(
	name: string,
	points: TrackPoint[],
	waypoints: Waypoint[] = [],
	source = ''
): string {
	const wpts = waypoints
		.map(
			(w) =>
				`  <wpt lat="${w.lat.toFixed(6)}" lon="${w.lon.toFixed(6)}">${
					w.ele != null ? `<ele>${Math.round(w.ele)}</ele>` : ''
				}<name>${esc(w.name)}</name></wpt>`
		)
		.join('\n');
	const trkpts = points
		.map(
			([lon, lat, ele]) =>
				`      <trkpt lat="${lat.toFixed(6)}" lon="${lon.toFixed(6)}"><ele>${Math.round(ele)}</ele></trkpt>`
		)
		.join('\n');
	return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Cordata" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>${esc(name)}</name>${source ? `<desc>${esc(source)}</desc>` : ''}</metadata>
${wpts ? wpts + '\n' : ''}  <trk>
    <name>${esc(name)}</name>
    <trkseg>
${trkpts}
    </trkseg>
  </trk>
</gpx>
`;
}

export function toKml(name: string, points: TrackPoint[], source = ''): string {
	const coords = points
		.map(([lon, lat, ele]) => `${lon.toFixed(6)},${lat.toFixed(6)},${Math.round(ele)}`)
		.join(' ');
	return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${esc(name)}</name>${source ? `\n    <description>${esc(source)}</description>` : ''}
    <Placemark>
      <name>${esc(name)}</name>
      <LineString><altitudeMode>clampToGround</altitudeMode><coordinates>${coords}</coordinates></LineString>
    </Placemark>
  </Document>
</kml>
`;
}

export function fileName(title: string, ext: 'gpx' | 'kml'): string {
	const base = title
		.toLowerCase()
		.normalize('NFD')
		.replace(/[̀-ͯ]/g, '')
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '')
		.slice(0, 60);
	return `${base || 'traccia'}.${ext}`;
}

/** Scarica un testo come file (solo nel browser). */
export function download(text: string, name: string, type: string): void {
	const url = URL.createObjectURL(new Blob([text], { type }));
	const a = document.createElement('a');
	a.href = url;
	a.download = name;
	document.body.appendChild(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}
