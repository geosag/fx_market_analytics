------------------------------------------------------------------------------------
-- ROLE CREATION
------------------------------------------------------------------------------------

-- Create role writer that will be assigned to the Python script
CREATE ROLE writer WITH LOGIN PASSWORD -- + 'PASSWORD';

-- Create role reader that will be assigned to Power BI
CREATE ROLE reader WITH LOGIN PASSWORD -- + 'PASSWORD';

------------------------------------------------------------------------------------
-- PERMISSIONS
------------------------------------------------------------------------------------

-- Grant usage permission on public schema to writer role
GRANT USAGE ON SCHEMA public TO writer;

-- Grant usage permission on public schema to reader role
GRANT USAGE ON SCHEMA public TO reader;

-- Permissions to grant to writer role 
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO writer;

-- Permissions to grant to writer role 
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reader;

------------------------------------------------------------------------------------
-- RLS --> ON: POLICIES FOR THE DIFFERENT ROLES IN EACH OF THE TABLES
------------------------------------------------------------------------------------

-- Allow writer to do everything on currencies_daily_data
CREATE POLICY "writer_all" ON currencies_daily_data
FOR ALL
TO writer
USING (true)
WITH CHECK (true);
  
-- Allow writer to do everything on currencies_weekly_data
CREATE POLICY "writer_all" ON currencies_weekly_data
FOR ALL
TO writer
USING (true)
WITH CHECK (true);
  
-- Allow writer to do everything on currencies_monthly_data
CREATE POLICY "writer_all" ON currencies_monthly_data
FOR ALL
TO writer
USING (true)
WITH CHECK (true);

-- Allow reader to only read on currencies_daily_data
CREATE POLICY "reader_select" ON currencies_daily_data
FOR SELECT
TO reader
USING (true);
  
-- Allow reader to only read on currencies_weekly_data
CREATE POLICY "reader_select" ON currencies_weekly_data
FOR SELECT
TO reader
USING (true);
  
-- Allow reader to only read on currencies_monthly_data
CREATE POLICY "reader_select" ON currencies_monthly_data
FOR SELECT
TO reader
USING (true);
