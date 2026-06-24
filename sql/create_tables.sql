-- =============================================================================
-- Supabase schema - written for a clinic, can be altered to match the needs of other businesses.
--
-- IMPORTANT: Select ALL of this file and run it once (Ctrl+A → Run).
-- Do NOT run only the seed block at the bottom — that causes:
--   ERROR: relation "slots" does not exist
--
-- Safe to re-run: uses IF NOT EXISTS / conditional blocks throughout.
-- =============================================================================

create extension if not exists "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. customers — caller memory
-- -----------------------------------------------------------------------------
create table if not exists customers (
    phone                   text primary key,
    name                    text,
    preferred_doctor        text,
    last_booking_id         text,
    last_appointment_date   text,
    last_appointment_time   text,
    call_count              integer not null default 1,
    first_seen              timestamptz not null default now(),
    last_seen               timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- 2. slots — availability + bookings (required for book / cancel / reschedule)
-- -----------------------------------------------------------------------------
create table if not exists slots (
    id              uuid primary key default gen_random_uuid(),
    doctor          text not null,
    iso_date        date not null,
    iso_time        time not null,
    status          text not null default 'available',
    booking_id      text,
    patient_name    text,
    phone           text,
    reason          text,
    cancelled_at    timestamptz,
    created_at      timestamptz not null default now(),
    constraint slots_status_check check (status in ('available', 'booked')),
    constraint slots_doctor_check check (
        doctor in ('Dr. Meera Nair', 'Dr. Arun Sharma')
    ),
    constraint slots_unique_doctor_datetime unique (doctor, iso_date, iso_time)
);

-- -----------------------------------------------------------------------------
-- 3. appointments — booking audit log
-- -----------------------------------------------------------------------------
create table if not exists appointments (
    id               text primary key,
    phone            text not null,
    doctor           text,
    date             text,
    time             text,
    reason           text,
    booking_id       text,
    status           text not null default 'confirmed',
    rescheduled_from text,
    created_at       timestamptz not null default now(),
    constraint appointments_status_check check (
        status in ('confirmed', 'cancelled', 'rescheduled')
    )
);

-- -----------------------------------------------------------------------------
-- 4. call_logs — transcripts
-- -----------------------------------------------------------------------------
create table if not exists call_logs (
    id               uuid primary key default gen_random_uuid(),
    phone            text,
    started_at       timestamptz default now(),
    ended_at         timestamptz,
    duration_seconds integer,
    transcript       jsonb,
    booking_id       text,
    intent           text,
    call_outcome     text,
    created_at       timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------------
create index if not exists idx_slots_available
    on slots (doctor, iso_date, iso_time)
    where status = 'available';

create index if not exists idx_slots_phone_booked
    on slots (phone, iso_date, iso_time)
    where status = 'booked';

create index if not exists idx_slots_booking_id
    on slots (booking_id)
    where booking_id is not null;

create index if not exists idx_appointments_phone_status
    on appointments (phone, status);

create index if not exists idx_appointments_booking_id
    on appointments (booking_id);

create index if not exists idx_call_logs_phone
    on call_logs (phone);

create index if not exists idx_call_logs_started_at
    on call_logs (started_at desc);

-- -----------------------------------------------------------------------------
-- 5. Upgrades for databases created from an older script (skipped if table missing)
-- -----------------------------------------------------------------------------
do $$
begin
    if exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'slots'
    ) then
        alter table slots add column if not exists cancelled_at timestamptz;
    end if;

    if exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'appointments'
    ) then
        alter table appointments add column if not exists status text default 'confirmed';
        alter table appointments add column if not exists rescheduled_from text;
    end if;

    if exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'customers'
    ) then
        alter table customers add column if not exists first_seen timestamptz default now();
    end if;
end $$;

-- -----------------------------------------------------------------------------
-- 6. Seed sample slots (only runs if slots table exists)
-- Mon–Sat, 09:00–13:00 and 17:00–20:00, 30 minutes, both doctors, 14 days
-- -----------------------------------------------------------------------------
do $$
begin
    if not exists (
        select 1 from information_schema.tables
        where table_schema = 'public' and table_name = 'slots'
    ) then
        raise exception
            'Table "slots" is missing. Run this entire file from the top (Ctrl+A → Run), not just the seed block.';
    end if;

    insert into slots (doctor, iso_date, iso_time, status)
    select
        d.doctor,
        days.slot_date,
        t.slot_time,
        'available'
    from (
        values
            ('Dr. Meera Nair'),
            ('Dr. Arun Sharma')
    ) as d(doctor)
    cross join lateral (
        select (current_date + gs.i)::date as slot_date
        from generate_series(0, 13) as gs(i)
    ) as days
    cross join lateral (
        select time '09:00' as slot_time
        union all select time '09:30'
        union all select time '10:00'
        union all select time '10:30'
        union all select time '11:00'
        union all select time '11:30'
        union all select time '12:00'
        union all select time '12:30'
        union all select time '17:00'
        union all select time '17:30'
        union all select time '18:00'
        union all select time '18:30'
        union all select time '19:00'
        union all select time '19:30'
    ) as t
    where extract(isodow from days.slot_date) between 1 and 6
    on conflict (doctor, iso_date, iso_time) do nothing;

    raise notice 'Seed complete. Available slots: %',
        (select count(*) from slots where status = 'available');
end $$;