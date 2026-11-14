import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MAX_UPLOAD_BYTES, parseUpload } from '../lib/geojsonUpload';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GeoJsonUpload } from './GeoJsonUpload';

const square = (s: number) => ({
  type: 'Polygon',
  coordinates: [
    [
      [110, 0],
      [110 + s, 0],
      [110 + s, s],
      [110, s],
      [110, 0],
    ],
  ],
});
const fc = (...geoms: unknown[]) =>
  JSON.stringify({
    type: 'FeatureCollection',
    features: geoms.map((g) => ({ type: 'Feature', properties: {}, geometry: g })),
  });

describe('parseUpload', () => {
  const parse = (text: string, size = text.length) => parseUpload(text, 'area.geojson', size, 1e6);

  it('accepts one polygon as a FeatureCollection, Feature or bare geometry', () => {
    const a = parse(fc(square(1)));
    expect(a).toMatchObject({ ok: true, aoi: { kind: 'upload', label: 'area' } });
    expect(parse(JSON.stringify({ type: 'Feature', geometry: square(1) })).ok).toBe(true);
    expect(parse(JSON.stringify(square(1))).ok).toBe(true);
  });

  it('rejects wrong formats with specific errors', () => {
    expect(parse('{"oops"')).toMatchObject({ error: 'upload.err.json' });
    expect(parse(fc(square(1), square(2)))).toMatchObject({ error: 'upload.err.count' });
    expect(parse(fc({ type: 'Point', coordinates: [1, 2] }))).toMatchObject({
      error: 'upload.err.type',
    });
    expect(
      parse(
        fc({
          type: 'Polygon',
          coordinates: [
            [
              [200, 0],
              [201, 0],
              [201, 1],
              [200, 0],
            ],
          ],
        }),
      ),
    ).toMatchObject({ error: 'upload.err.coords' });
    expect(parse(fc(square(15)))).toMatchObject({ error: 'upload.err.tooLarge' });
    expect(parse(fc(square(1)), MAX_UPLOAD_BYTES + 1)).toMatchObject({ error: 'upload.err.size' });
    expect(parse('[1, 2]')).toMatchObject({ error: 'upload.err.notGeojson' });
  });
});

describe('GeoJsonUpload', () => {
  beforeEach(() => {
    useAppStore.setState({ aoi: null });
    mockFetch({ '/meta': META_OK });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('sets the uploaded polygon as the AOI', async () => {
    renderWithQuery(<GeoJsonUpload />);
    const file = new File([fc(square(2))], 'peatland.geojson', { type: 'application/geo+json' });
    fireEvent.change(screen.getByLabelText('Upload GeoJSON'), { target: { files: [file] } });
    await waitFor(() => expect(useAppStore.getState().aoi?.label).toBe('peatland'));
  });

  it('explains why a file was rejected', async () => {
    renderWithQuery(<GeoJsonUpload />);
    const file = new File([fc(square(1), square(1))], 'two.geojson');
    fireEvent.change(screen.getByLabelText('Upload GeoJSON'), { target: { files: [file] } });
    expect(await screen.findByRole('alert')).toHaveTextContent('exactly one polygon');
    expect(useAppStore.getState().aoi).toBeNull();
  });
});
