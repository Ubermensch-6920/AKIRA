import React, { useState } from "react";

const NAV_ITEMS = [
  "Summary",
  "Reserves",
  "Development",
  "Drill-Down",
  "Assumptions",
  "Runs",
];

function Sidebar({ active, onSelect }) {
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-muted/40 p-4">
      <div className="mb-6 px-2">
        <div className="text-lg font-semibold">AKIRA</div>
        <div className="text-xs text-muted-foreground">Actuarial Model</div>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <button
            key={item}
            onClick={() => onSelect(item)}
            className={
              "rounded-md px-3 py-2 text-left text-sm transition-colors " +
              (active === item
                ? "bg-primary text-primary-foreground"
                : "text-foreground hover:bg-muted")
            }
          >
            {item}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function Placeholder({ section }) {
  return (
    <div className="flex h-full flex-col gap-4 p-8">
      <h1 className="text-2xl font-semibold">{section}</h1>
      <p className="text-sm text-muted-foreground">
        Phase 1 scaffold. Data wiring arrives in a follow-up.
      </p>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-lg border border-border bg-background p-4"
          >
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              KPI {i}
            </div>
            <div className="mt-2 text-2xl font-semibold">—</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState("Summary");
  return (
    <div className="flex h-full">
      <Sidebar active={active} onSelect={setActive} />
      <main className="flex-1 overflow-auto">
        <Placeholder section={active} />
      </main>
    </div>
  );
}
