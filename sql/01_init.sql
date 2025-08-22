create table if not exists public.locations (
  id bigserial primary key,
  label text not null,
  lat numeric(9,6) not null,
  lon numeric(9,6) not null,
  provider text default 'geocodify',
  provider_ref text
);

create unique index if not exists ux_locations_lat_lon on public.locations(lat, lon);

create table if not exists public.weather_requests (
  id bigserial primary key,
  location_id bigint not null references public.locations(id) on delete cascade,
  start_date date not null,
  end_date date not null,
  unit text not null default 'fahrenheit',
  created_at timestamptz not null default now()
);