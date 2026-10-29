import type { CompareResponse } from "@/lib/types";

/**
 * The comparison. Every word and figure is the engine's (it reads them from the data release); this only lays them
 * out. A cell that the maker has not stated reads "Not stated by maker". A category with no fair winner says why.
 */
export default function CompareView({ data }: { data: CompareResponse }) {
  const { cars } = data;
  const leads = cars.map((car) => ({
    car,
    categories: data.winners.filter((w) => w.variant_key === car.variant_key),
  }));
  const withheld = data.winners.filter((w) => w.variant_key === null);

  return (
    <div className="flex flex-col gap-6">
      <section aria-label="Where each car leads" className="no-break flex flex-col gap-4 rounded-[18px] border border-line bg-white p-5 md:p-6">
        <h2 className="m-0 text-xl font-extrabold">Where each car leads</h2>
        <div className={`grid gap-3 ${cars.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
          {leads.map(({ car, categories }) => (
            <div key={car.variant_key} className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4">
              <h3 className="m-0 text-[16px] font-extrabold">{car.name}</h3>
              {categories.length > 0 ? (
                <ul className="m-0 flex list-none flex-col gap-2 p-0">
                  {categories.map((w) => (
                    <li key={w.category} className="rounded-lg border border-good/30 bg-good-bg p-2.5 text-[14px] text-good-ink">
                      <span className="font-extrabold">{w.label}.</span> {w.text}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="m-0 text-[14px] text-muted">Does not lead on any measure where a fair comparison is possible.</p>
              )}
            </div>
          ))}
        </div>
        {withheld.length > 0 ? (
          <div className="flex flex-col gap-2">
            <h3 className="m-0 text-[15px] font-extrabold">No clear leader</h3>
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {withheld.map((w) => (
                <li key={w.category} className="text-[14px] text-muted">
                  <span className="font-bold text-ink">{w.label}.</span> {w.text}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section aria-label="Side by side" className="no-break flex flex-col gap-3.5 rounded-[18px] border border-line bg-white p-5 md:p-6">
        <h2 className="m-0 text-xl font-extrabold">Side by side</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead>
              <tr className="text-left">
                <th className="w-[26%] border-b-2 border-line p-2.5" scope="col">
                  <span className="sr-only">Measure</span>
                </th>
                {cars.map((car) => (
                  <th key={car.variant_key} scope="col" className="border-b-2 border-brand p-2.5 align-bottom font-extrabold">
                    {car.name}
                    <span className="block text-[12px] font-semibold text-muted">
                      {car.body_type}
                      {car.pricing_type === "BaaS" ? ", battery rental" : ""}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            {data.sections.map((section) => (
              <tbody key={section.title}>
                <tr>
                  <th colSpan={cars.length + 1} scope="colgroup" className="bg-surface p-2.5 text-left text-[13px] font-extrabold uppercase tracking-wide text-muted">
                    {section.title}
                  </th>
                </tr>
                {section.rows.map((row) => (
                  <tr key={row.key}>
                    <th scope="row" className="border-b border-chip p-2.5 text-left align-top font-bold">
                      {row.label}
                    </th>
                    {row.cells.map((cell, i) => (
                      <td
                        key={cars[i]?.variant_key ?? i}
                        className={`border-b border-chip p-2.5 align-top ${cell.best ? "bg-good-bg font-semibold text-good-ink" : ""} ${
                          cell.state === "not_stated" ? "italic text-muted" : ""
                        }`}
                      >
                        {cell.text}
                        {cell.best ? <span className="mt-0.5 block text-[11px] font-extrabold uppercase tracking-wide">Leads here</span> : null}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
      </section>

      <section aria-label="Watch-outs" className="no-break flex flex-col gap-3 rounded-[18px] border border-warn-line bg-warn-bg p-5 md:p-6">
        <h2 className="m-0 text-xl font-extrabold text-warn-ink">Watch-outs</h2>
        <div className={`grid gap-3 ${cars.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
          {cars.map((car) => {
            const items = data.watch_outs.find((w) => w.variant_key === car.variant_key)?.items ?? [];
            return (
              <div key={car.variant_key}>
                <h3 className="m-0 mb-1.5 text-[15px] font-extrabold">{car.name}</h3>
                {items.length > 0 ? (
                  <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-[14px] text-warn-ink">
                    {items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="m-0 text-[14px] text-warn-ink">None flagged in our data.</p>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section aria-label="Notes" className="flex flex-col gap-2 text-[14px] text-muted">
        {data.notes.map((note) => (
          <p key={note} className="m-0">
            {note}
          </p>
        ))}
        <p className="m-0">{data.disclaimer}</p>
      </section>
    </div>
  );
}
