import { outsideAoiMask } from './aoi';

describe('outside AOI mask', () => {
  it('cuts every selected island out of the dark overlay', () => {
    const square = (x: number) => [
      [
        [x, 0],
        [x + 1, 0],
        [x + 1, 1],
        [x, 1],
        [x, 0],
      ],
    ];
    const mask = outsideAoiMask({
      type: 'MultiPolygon',
      coordinates: [square(100), square(110)],
    });
    expect(mask.geometry.type).toBe('MultiPolygon');
    expect(mask.geometry.coordinates[0]).toHaveLength(3);
    expect(mask.geometry.coordinates[0]![0]![0]).toEqual([-180, -85]);
  });
});
