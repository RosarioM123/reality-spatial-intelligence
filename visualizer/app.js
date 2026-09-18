/* REALITY world visualizer — Vue 3 (global build), no bundler.
 *
 * Loads sample-world.json (a SpatialWorld dict exported by the Python
 * library), renders zones/entities/routes on SVG, and answers a small
 * subset of the ask() question shapes in the browser. The query engine
 * here is intentionally tiny and mirrors the Python queries.py API:
 * same patterns, same JSON answer shapes.
 */

const { createApp } = Vue;

function centroidOf(polygon) {
  // polygon: [[x, y, z?], ...] — area-weighted centroid, x/y only.
  let cx = 0, cy = 0, signed = 0;
  const n = polygon.length;
  for (let i = 0; i < n; i++) {
    const [ax, ay] = polygon[i];
    const [bx, by] = polygon[(i + 1) % n];
    const cross = ax * by - bx * ay;
    signed += cross;
    cx += (ax + bx) * cross;
    cy += (ay + by) * cross;
  }
  if (Math.abs(signed) < 1e-9) {
    const sx = polygon.reduce((s, p) => s + p[0], 0) / n;
    const sy = polygon.reduce((s, p) => s + p[1], 0) / n;
    return [sx, sy];
  }
  return [cx / (3 * signed), cy / (3 * signed)];
}

const app = createApp({
  data() {
    return {
      zones: {},        // id -> {id, name, polygon, floor, cx, cy}
      entities: {},     // id -> {id, name, kind, position, zone_id, state}
      adjacency: {},
      loaded: false,
      loadError: null,
      tab: "details",
      selected: null,   // selected entity object
      layers: { zones: true, entities: true, routes: true, labels: true },
      routeFrom: null,
      routeTo: null,
      routePath: null,  // [zoneId, ...]
      routeInfo: null,
      queryText: "",
      queryResult: null,
      dotR: 0.4,
      labelSize: 1,
      presets: [
        "where is reception desk?",
        "list zones",
        "list entities of kind workstation",
        "route from lobby to office b",
        "what is near reception desk within 8?",
      ],
    };
  },

  computed: {
    zoneList() { return Object.values(this.zones); },
    entityList() { return Object.values(this.entities); },

    viewBox() {
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const z of this.zoneList) {
        for (const [x, y] of z.polygon) {
          if (x < minX) minX = x;
          if (y < minY) minY = y;
          if (x > maxX) maxX = x;
          if (y > maxY) maxY = y;
        }
      }
      const pad = Math.max(maxX - minX, maxY - minY) * 0.08 + 1;
      return `${minX - pad} ${minY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`;
    },

    routePoints() {
      if (!this.routePath) return null;
      return this.routePath
        .map((id) => this.zones[id])
        .filter(Boolean)
        .map((z) => `${z.cx},${z.cy}`)
        .join(" ");
    },

    routeStops() {
      if (!this.routePath) return [];
      return this.routePath
        .map((id) => this.zones[id])
        .filter(Boolean)
        .map((z) => [z.cx, z.cy]);
    },
  },

  methods: {
    async load() {
      try {
        const res = await fetch("sample-world.json");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        for (const z of data.zones || []) {
          const [cx, cy] = centroidOf(z.polygon);
          this.zones[z.id] = { ...z, cx, cy };
        }
        for (const e of data.entities || []) {
          this.entities[e.id] = e;
        }
        this.adjacency = data.adjacency || {};
        const ids = Object.keys(this.zones);
        this.routeFrom = ids[0] || null;
        this.routeTo = ids[ids.length - 1] || null;
        // Scale glyph sizes to the world extents so the map reads at any scale.
        const vb = this.viewBox.split(" ").map(Number);
        const span = Math.max(vb[2], vb[3]);
        this.dotR = Math.max(0.12, span * 0.007);
        this.labelSize = Math.max(0.5, span * 0.022);
        this.loaded = true;
      } catch (err) {
        this.loadError = `Could not load sample-world.json: ${err.message}`;
      }
    },

    svgPoints(polygon) {
      return polygon.map(([x, y]) => `${x},${y}`).join(" ");
    },

    fmt(n) { return Math.round(n * 100) / 100; },
    pretty(obj) { return JSON.stringify(obj, null, 2); },
    zoneName(id) {
      return (this.zones[id] && this.zones[id].name) || id || "—";
    },

    selectEntity(id) { this.selected = this.entities[id] || null; },

    focusZone(id) {
      // Clicking a zone seeds the route planner's origin.
      if (this.tab === "details") this.routeFrom = id;
    },

    // -- routing (BFS over the zone adjacency graph) ---------------------
    findRoute() {
      const from = this.routeFrom, to = this.routeTo;
      this.routePath = null;
      this.routeInfo = null;
      if (!from || !to || !this.zones[from] || !this.zones[to]) {
        this.routeInfo = "Pick two known zones.";
        return;
      }
      if (from === to) {
        this.routePath = [from];
        this.routeInfo = "Already there — zero hops.";
        return;
      }
      const prev = { [from]: null };
      const queue = [from];
      let found = false;
      while (queue.length && !found) {
        const cur = queue.shift();
        for (const nxt of this.adjacency[cur] || []) {
          if (!(nxt in prev) && this.zones[nxt]) {
            prev[nxt] = cur;
            if (nxt === to) { found = true; break; }
            queue.push(nxt);
          }
        }
      }
      if (!found) {
        this.routeInfo = `No connected path from ${this.zoneName(from)} to ${this.zoneName(to)}.`;
        return;
      }
      const path = [to];
      while (prev[path[path.length - 1]] !== null) {
        path.push(prev[path[path.length - 1]]);
      }
      this.routePath = path.reverse();
      const names = this.routePath.map((id) => this.zoneName(id));
      this.routeInfo = `${names.join(" → ")} (${this.routePath.length - 1} hops)`;
    },

    clearRoute() {
      this.routePath = null;
      this.routeInfo = null;
    },

    // -- mini query engine (mirrors queries.py patterns) -----------------
    findEntity(ref) {
      ref = ref.trim().toLowerCase();
      return this.entityList.find(
        (e) => e.id.toLowerCase() === ref || e.name.toLowerCase() === ref
      ) || null;
    },

    findZone(ref) {
      ref = ref.trim().toLowerCase();
      const z = this.zoneList.find(
        (z) => z.id.toLowerCase() === ref || z.name.toLowerCase() === ref
      );
      return z ? z.id : null;
    },

    runQuery() {
      const q = this.queryText.trim();
      const low = q.toLowerCase();
      let m, ans;

      if ((m = low.match(/^where is (.+?)\??$/))) {
        const e = this.findEntity(m[1]);
        ans = e
          ? { type: "entity_location", query: q, entity: this.entityJSON(e),
              zone_id: e.zone_id, zone_name: this.zoneName(e.zone_id) }
          : { type: "not_found", query: q,
              message: `no entity matching '${m[1].trim()}'` };
      } else if ((m = low.match(/^what(?:'s| is) near (.+?)(?: within ([\d.]+))?\??$/))) {
        const e = this.findEntity(m[1]);
        if (!e) {
          ans = { type: "not_found", query: q,
                  message: `no entity matching '${m[1].trim()}'` };
        } else {
          const radius = m[2] ? parseFloat(m[2]) : 5.0;
          const [ex, ey] = e.position;
          const results = this.entityList
            .filter((o) => o.id !== e.id)
            .map((o) => ({
              entity: this.entityJSON(o),
              distance: Math.round(
                Math.hypot(o.position[0] - ex, o.position[1] - ey) * 1000) / 1000,
            }))
            .filter((h) => h.distance <= radius)
            .sort((a, b) => a.distance - b.distance);
          ans = { type: "nearby", query: q, origin: this.entityJSON(e),
                  radius, results };
        }
      } else if ((m = low.match(/^list (zones|entities)(?: of kind (\w+))?\??$/))) {
        ans = m[1] === "zones"
          ? { type: "zone_list", query: q,
              zones: this.zoneList.map((z) => ({
                id: z.id, name: z.name, floor: z.floor,
                area: Math.round(this.zoneArea(z) * 100) / 100 })) }
          : { type: "entity_list", query: q, kind: m[2] || null,
              entities: this.entityList
                .filter((e) => !m[2] || e.kind === m[2])
                .map((e) => this.entityJSON(e)) };
      } else if ((m = low.match(/^(?:route|path|how do i get) from (.+?) to (.+?)\??$/))) {
        const from = this.findZone(m[1]), to = this.findZone(m[2]);
        if (!from || !to) {
          ans = { type: "not_found", query: q,
                  message: "unknown zone in route request" };
        } else {
          const path = this.bfs(from, to);
          ans = path
            ? { type: "route", query: q, from, to, path,
                path_names: path.map((id) => this.zoneName(id)),
                hops: path.length - 1 }
            : { type: "no_route", query: q, from, to,
                message: "no connected path between zones" };
          if (path) {
            this.routeFrom = from; this.routeTo = to;
            this.routePath = path;
            this.routeInfo = `${path.map((id) => this.zoneName(id)).join(" → ")}`;
          }
        }
      } else {
        ans = { type: "unrecognized", query: q,
                message: "could not parse as a spatial question",
                hint: "try: 'where is <entity>', 'what is near <entity>', "
                  + "'list zones', 'list entities of kind <kind>', "
                  + "'route from <a> to <b>'" };
      }
      this.queryResult = JSON.stringify(ans, null, 2);
    },

    entityJSON(e) {
      return { id: e.id, name: e.name, kind: e.kind,
               position: { x: e.position[0], y: e.position[1],
                           z: e.position[2] || 0 },
               zone_id: e.zone_id, state: e.state || {} };
    },

    zoneArea(z) {
      let area = 0;
      const p = z.polygon, n = p.length;
      for (let i = 0; i < n; i++) {
        const [ax, ay] = p[i], [bx, by] = p[(i + 1) % n];
        area += ax * by - bx * ay;
      }
      return Math.abs(area) / 2;
    },

    bfs(from, to) {
      if (from === to) return [from];
      const prev = { [from]: null };
      const queue = [from];
      while (queue.length) {
        const cur = queue.shift();
        for (const nxt of this.adjacency[cur] || []) {
          if (!(nxt in prev) && this.zones[nxt]) {
            prev[nxt] = cur;
            if (nxt === to) {
              const path = [to];
              while (prev[path[path.length - 1]] !== null) {
                path.push(prev[path[path.length - 1]]);
              }
              return path.reverse();
            }
            queue.push(nxt);
          }
        }
      }
      return null;
    },
  },

  mounted() { this.load(); },
});

app.mount("#app");
