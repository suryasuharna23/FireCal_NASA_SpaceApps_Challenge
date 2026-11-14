/**
 * jsdom has no WebGL, so MapLibre and Terra Draw are replaced by light fakes that
 * record calls. Import this module (vi.mock is hoisted) in tests that render maps.
 */
type Handler = (...args: unknown[]) => void;

export const mapCalls: { fitBounds: unknown[]; setData: unknown[] } = {
  fitBounds: [],
  setData: [],
};

export class FakeMap {
  static last: FakeMap | null = null;
  handlers: Record<string, Handler[]> = {};
  sources: Record<string, { setData: (d: unknown) => void }> = {};
  constructor() {
    FakeMap.last = this;
    queueMicrotask(() => this.handlers.load?.forEach((h) => h()));
  }
  on(event: string, handler: Handler) {
    (this.handlers[event] ??= []).push(handler);
    return this;
  }
  off() {
    return this;
  }
  once(event: string, handler: Handler) {
    return this.on(event, handler);
  }
  addControl() {
    return this;
  }
  addSource(id: string) {
    this.sources[id] = { setData: (d) => mapCalls.setData.push(d) };
  }
  getSource(id: string) {
    return this.sources[id];
  }
  addLayer() {}
  getLayer() {
    return undefined;
  }
  removeLayer() {}
  setLayoutProperty() {}
  setPaintProperty() {}
  fitBounds(b: unknown) {
    mapCalls.fitBounds.push(b);
  }
  setProjection() {}
  setSky() {}
  getStyle() {
    return { layers: [] };
  }
  getZoom() {
    return 1.5;
  }
  getCenter() {
    return { lng: 0, lat: 0 };
  }
  setCenter() {}
  isMoving() {
    return false;
  }
  flyTo() {}
  getCanvas() {
    return document.createElement('canvas');
  }
  resize() {}
  remove() {}
}

export class FakeDraw {
  static last: FakeDraw | null = null;
  mode = 'static';
  features: Record<string, unknown>[] = [];
  handlers: Record<string, Handler[]> = {};
  constructor() {
    FakeDraw.last = this;
  }
  start() {}
  stop() {}
  setMode(mode: string) {
    this.mode = mode;
  }
  on(event: string, handler: Handler) {
    (this.handlers[event] ??= []).push(handler);
  }
  getSnapshot() {
    return this.features;
  }
  getSnapshotFeature(id: string) {
    return this.features.find((f) => f.id === id);
  }
  removeFeatures(ids: string[]) {
    this.features = this.features.filter((f) => !ids.includes(f.id as string));
  }
  clear() {
    this.features = [];
  }
  selectFeature() {}
  /** Simulate the user finishing a drawing. */
  finish(feature: Record<string, unknown>) {
    this.features.push(feature);
    this.handlers.finish?.forEach((h) => h(feature.id, { action: 'draw' }));
  }
}

vi.mock('maplibre-gl', () => ({
  default: { Map: FakeMap, NavigationControl: class {}, Popup: class {} },
}));
vi.mock('maplibre-gl/dist/maplibre-gl.css', () => ({}));
vi.mock('terra-draw', () => ({
  TerraDraw: FakeDraw,
  TerraDrawPolygonMode: class {},
  TerraDrawRectangleMode: class {},
  TerraDrawSelectMode: class {},
}));
vi.mock('terra-draw-maplibre-gl-adapter', () => ({ TerraDrawMapLibreGLAdapter: class {} }));
