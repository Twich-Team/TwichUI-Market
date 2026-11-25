import type { CrateCatalogue } from "./waylaid-crates-data";

export function CrateAttribution({ catalogue }: { catalogue: CrateCatalogue }) {
  return <small className="waylaid-attribution">
    Crate catalogue from <a href={catalogue.source_url || "https://foreverdb.net"} target="_blank" rel="noreferrer">ForeverDB</a>
    {catalogue.build && <> · Build {catalogue.build}</>}
  </small>;
}
