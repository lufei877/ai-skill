# Invoice service fixture

Synthetic local Python service with no network or real customer data. The HTTP adapter is outside this fixture; it authenticates sessions and passes the numeric user ID to gateway.invoice. Database connections implement the sqlite3 interface. pricing.quote feeds the checkout preview and pricing.charge feeds settlement. export_job.run writes an export using the supplied writer.
