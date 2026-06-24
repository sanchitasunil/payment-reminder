import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const DOCTORS = ["Dr. Meera Nair", "Dr. Arun Sharma"];
const MORNING_SLOTS = [
  "09:00",
  "09:30",
  "10:00",
  "10:30",
  "11:00",
  "11:30",
  "12:00",
  "12:30",
];
const EVENING_SLOTS = [
  "17:00",
  "17:30",
  "18:00",
  "18:30",
  "19:00",
  "19:30",
];
const ALL_SLOTS = [...MORNING_SLOTS, ...EVENING_SLOTS];
const MIN_DAYS_AHEAD = 30;
const SEED_DAYS = 60;

function toDateOnly(d: Date): string {
  return d.toISOString().split("T")[0];
}

Deno.serve(async () => {
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  const { data: latestRow } = await supabase
    .from("slots")
    .select("iso_date")
    .order("iso_date", { ascending: false })
    .limit(1)
    .single();

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const latestDate = latestRow?.iso_date
    ? new Date(latestRow.iso_date as string)
    : new Date(today);

  const daysAhead = Math.floor(
    (latestDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (daysAhead >= MIN_DAYS_AHEAD) {
    return new Response(
      JSON.stringify({
        message: `Slots OK — ${daysAhead} days ahead. No seeding needed.`,
      }),
      { headers: { "Content-Type": "application/json" } },
    );
  }

  const seedFrom = new Date(latestDate);
  seedFrom.setDate(seedFrom.getDate() + 1);

  const seedUntil = new Date(today);
  seedUntil.setDate(seedUntil.getDate() + SEED_DAYS);

  const rows: {
    doctor: string;
    iso_date: string;
    iso_time: string;
    status: string;
  }[] = [];
  const cursor = new Date(seedFrom);

  while (cursor <= seedUntil) {
    const dow = cursor.getDay(); // 0 = Sunday
    if (dow !== 0) {
      const dateStr = toDateOnly(cursor);
      for (const doctor of DOCTORS) {
        for (const slotStart of ALL_SLOTS) {
          rows.push({
            doctor,
            iso_date: dateStr,
            iso_time: slotStart.length === 5 ? `${slotStart}:00` : slotStart,
            status: "available",
          });
        }
      }
    }
    cursor.setDate(cursor.getDate() + 1);
  }

  const { error } = await supabase.from("slots").upsert(rows, {
    onConflict: "doctor,iso_date,iso_time",
    ignoreDuplicates: true,
  });

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(
    JSON.stringify({
      message: `Seeded ${rows.length} slots from ${toDateOnly(seedFrom)} to ${toDateOnly(seedUntil)}`,
    }),
    { headers: { "Content-Type": "application/json" } },
  );
});
