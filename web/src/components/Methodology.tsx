import { useMeta } from '../api/client';

/** Signed percentage with two decimals, e.g. "+0.01%" (bias is usually small). */
const biasPct = (bias: number) => `${bias >= 0 ? '+' : '−'}${Math.abs(bias * 100).toFixed(2)}%`;

const FIRMS_URL = 'https://firms.modaps.eosdis.nasa.gov';

/**
 * Methodology and attribution page (FR-W-20, NFR-10): data sources, filters,
 * harmonization, hold-out validation results, definitions and limitations.
 * Numbers come from /meta so the page always matches the deployed data.
 */
export function Methodology() {
  const { data: meta } = useMeta();
  const v = meta?.validation;
  const fmt = (x: number | null | undefined, digits = 3) =>
    x === null || x === undefined ? '–' : x.toFixed(digits);

  return (
    <article className="prose" aria-labelledby="methodology-title">
      <h2 id="methodology-title">Methodology</h2>
      <p className="lead">
        FireCal estimates a MODIS-equivalent monthly record from NASA FIRMS active-fire detections.
        Current dataset: {meta?.coverage?.country ?? 'configured coverage'},{' '}
        {meta?.start_month ?? '–'}
        {' to '}
        {meta?.end_month ?? '–'}. Model performance varies by region and period.
      </p>
      {meta?.dataset_status === 'experimental' ? (
        <p role="note">
          Experimental dataset. Review regional validation and source-version limitations before
          interpreting trends.
        </p>
      ) : null}

      <h3>1. Data sources</h3>
      <ul>
        <li>
          <strong>MODIS</strong> (Terra from November 2000, Aqua from July 2002), about 1 km pixels.
          {meta?.source_versions?.MODIS
            ? ` Reported MODIS versions: ${meta.source_versions.MODIS.join(', ')}.`
            : ''}
        </li>
        <li>
          <strong>VIIRS 375 m</strong> on supported S-NPP, NOAA-20 and NOAA-21 platforms.
          {meta?.coverage?.satellites
            ? ` Included satellites: ${meta.coverage.satellites.join(', ')}.`
            : ''}
        </li>
        <li>
          {meta?.coverage?.includes_nrt === false
            ? 'This dataset contains annual standard-processing archives. NRT data have not been appended.'
            : 'The pipeline supports near-real-time (NRT) updates. Months that contain NRT data are marked as provisional.'}
        </li>
      </ul>

      <h3>2. Cleaning</h3>
      <ul>
        <li>
          Confidence: MODIS detections need a confidence of at least 30; VIIRS detections need the{' '}
          <em>nominal</em> or <em>high</em> class.
        </li>
        <li>
          Only presumed vegetation fires are kept (FIRMS <code>type = 0</code>). Volcanoes, gas
          flares and other static heat sources are removed. For NRT data, which carry no type, a ~2
          km mask built from the archive's static sources is applied.
        </li>
      </ul>

      <h3>3. Gridding</h3>
      <p>
        Detections are counted per month on a global 0.25° grid ({meta?.grid_res_deg ?? 0.25}°),
        separately for each sensor. VIIRS counts are divided by the number of VIIRS satellites that
        delivered detections that month. This approximates satellite sampling; partial outages and
        changes in valid observation coverage can leave residual bias. Areas you select are summed
        from the cells they cover, with partly covered cells weighted by the share of their area
        inside the selection.
      </p>

      <h3>4. Harmonization</h3>
      <p>
        For each grid cell, a VIIRS → MODIS-equivalent ratio is estimated over the calibration
        period <strong>{meta?.calibration_period ?? '2013-01:2021-12'}</strong>, excluding the
        hold-out test years ({v?.test_years?.join(', ') ?? '–'}). Cell ratios are shrunk towards the
        ratio of their regional class (
        {meta?.coverage?.region_fallback ?? 'configured biome or fallback'}); cells with too few
        detections use the regional (or global) ratio directly. Up to{' '}
        <strong>{meta?.transition_month ?? '2021-12'}</strong> the series uses observed MODIS
        counts. After that it uses converted VIIRS counts with a 90 % uncertainty interval derived
        from the regional spread of monthly residuals. The calibration period starts after the 2012
        S-NPP ramp-up and ends before the Terra/Aqua orbit drift of 2022 onwards.
      </p>

      <h3>5. Validation</h3>
      <p>
        The calibrated model predicts MODIS from VIIRS in the hold-out years, which were not used
        for calibration. Monthly totals are compared with what MODIS actually observed. Targets:
        correlation r ≥ 0.9 and bias within ±10 %.
      </p>
      <table className="prose-table">
        <caption>{meta?.coverage?.country ?? 'Dataset'} hold-out validation</caption>
        <tbody>
          <tr>
            <th scope="row">Test years</th>
            <td>{v?.test_years?.join(', ') ?? '–'}</td>
          </tr>
          <tr>
            <th scope="row">Correlation r</th>
            <td>{fmt(v?.r)}</td>
          </tr>
          <tr>
            <th scope="row">Bias</th>
            <td>{v?.bias == null ? '–' : biasPct(v.bias)}</td>
          </tr>
          <tr>
            <th scope="row">Mean absolute error</th>
            <td>{fmt(v?.mae, 1)} detections / month</td>
          </tr>
          <tr>
            <th scope="row">Meets targets</th>
            <td>{v?.meets_target == null ? '–' : v.meets_target ? 'Yes' : 'No'}</td>
          </tr>
        </tbody>
      </table>
      {v?.limitations?.length ? (
        <>
          <p>Regions that miss the targets (treat their harmonized values with care):</p>
          <ul>
            {v.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </>
      ) : null}

      <h3>6. Definitions</h3>
      <ul>
        <li>
          <strong>Median</strong> and <strong>P25–P75</strong>: computed per calendar month over the
          reference years (default 2003–2022, adjustable).
        </li>
        <li>
          <strong>Anomaly</strong>: the change against that median in %. The{' '}
          <strong>percentile</strong> is the share of reference years with the same or a lower
          value.
        </li>
        <li>
          <strong>Fire season</strong>: months whose median is above the 75th percentile of all
          reference months in the area.
        </li>
      </ul>

      <h3>7. Limitations</h3>
      <ul>
        <li>
          Hotspots are satellite detections of active fire, not burned area. Clouds, smoke, canopy
          cover and short or small fires can hide fires.
        </li>
        <li>
          The harmonized scale is an estimate. Regions with sparse calibration data rely on regional
          fallback ratios. The 90 % interval reflects regional training residuals; its empirical
          coverage has not been verified.
        </li>
        <li>Recent months based on NRT data can change when standard data are published.</li>
        <li>Orbit drift and sensor degradation can leave residual trends.</li>
      </ul>

      <h3>8. Attribution and licence</h3>
      <p>
        We acknowledge the use of data from NASA&apos;s Fire Information for Resource Management
        System (<a href={FIRMS_URL}>FIRMS</a>), part of NASA&apos;s Earth Science Data and
        Information System (ESDIS). MODIS and VIIRS 375 m active-fire products. Every CSV and PNG
        export carries this attribution.
      </p>
      <p>
        FireCal&apos;s source code is released under the MIT licence. Data version{' '}
        <code>{meta?.data_version ?? '–'}</code>, last processed {meta?.last_updated ?? '–'}.
      </p>
    </article>
  );
}
