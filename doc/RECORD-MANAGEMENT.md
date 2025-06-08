# deSEC Qt DNS Manager: Record Management

This document provides information about managing DNS records in the deSEC Qt DNS Manager application.

## Record Types

The application supports all the record types offered by the deSEC API, including:

- **A/AAAA Records**: IPv4 and IPv6 address records
- **CNAME Records**: Canonical name records for aliasing
- **MX Records**: Mail exchange records for email routing
- **TXT Records**: Text records for various verification purposes
- **SRV Records**: Service records for specific services
- **NS Records**: Nameserver records
- And many more specialized types

For a complete list of supported record types, please refer to the deSEC API documentation or check the record type dropdown in the "Add Record" dialog.

## TTL Management

### Limitations

The deSEC DNS API enforces the following Time-To-Live (TTL) limitations:

- **Minimum TTL**: 3600 seconds (1 hour)
- **Maximum TTL**: 86400 seconds (24 hours)

These limitations are enforced by the deSEC API and cannot be bypassed within the application. If you need to set TTL values outside this range, you will need to contact deSEC directly to request account-specific adjustments.

### Available TTL Options

The application provides the following preset TTL options:

- 60 seconds (1 minute) - *may be rejected by API*
- 300 seconds (5 minutes) - *may be rejected by API*
- 600 seconds (10 minutes) - *may be rejected by API*
- 900 seconds (15 minutes) - *may be rejected by API*
- 1800 seconds (30 minutes) - *may be rejected by API*
- 3600 seconds (1 hour) - **recommended minimum**
- 7200 seconds (2 hours)
- 14400 seconds (4 hours)
- 86400 seconds (24 hours) - **maximum allowed**

Please note that while the application offers TTL values below 3600 seconds for special cases, the deSEC API will typically reject these values for standard accounts. If you need to set shorter TTLs, please contact [support@desec.io](mailto:support@desec.io) for account-specific adjustments and consider [supporting the project](https://desec.io/donate).

## Multiline Record Content

The deSEC Qt DNS Manager application supports entering multiple values for record content, with each value on a separate line. This is particularly useful for record types like NS, MX, TXT, A or AAAA records where you might have multiple values:

### Display Options

By default, the application shows only the first 3 lines of multiline records followed by a count of additional entries. This helps keep the interface clean and readable.

To view all content lines for multiline records:

1. Go to the **View** menu
2. Toggle the **Show Multiline Records** option

This setting is persisted across application restarts and applies to all record types. It's particularly useful when working with complex DNS configurations that have many entries per record type.

```text
10 mail1.example.com.
20 mail2.example.com.
```

While this syntax (multiple values separated by newlines) is not valid in a traditional zone file format, the deSEC API handles this appropriately by:

1. Accepting the multiline input as separate record values in the API request
2. Splitting these values into separate records on the DNS server side
3. Returning them as an array of records in subsequent API responses

This behavior is documented in the [deSEC API documentation](https://desec.readthedocs.io/en/latest/dns/rrsets.html), where the `records` field is defined as an array that can contain multiple values.

Using multiline input in the application provides convenience and feature parity with the deSEC web interface, allowing you to manage multiple values for a single record type in one operation.

## Record Management Operations

### Adding Records

To add a new DNS record:

1. Select a domain from the zone list
2. Click the "Add Record" button (or use keyboard shortcuts - see below)
3. Fill in the record details:
   - Subdomain (e.g., "www" or leave blank for apex record)
   - Record type (e.g., A, AAAA, CNAME)
   - TTL value
   - Record content (can enter multiple values, one per line)
4. Click "OK" to save the record

### Editing Records

To edit an existing record:

1. Select a domain from the zone list
2. Find the record in the records table
3. Either:
   - Click the "Edit" button for that record
   - Double-click on the record row
4. Update the record details
5. Click "OK" to save changes

### Deleting Records

To delete a record:

1. Select a domain from the zone list
2. Find the record in the records table
3. Either:
   - Click the "Delete" button for that record
   - Select the record and press the **Delete** key
4. Confirm the deletion when prompted

## Record Sorting and Filtering

### Sorting Records

The records table supports sorting by the following columns:

- **Name**: Sort by subdomain name (click column header)
- **Type**: Sort by record type (click column header)
- **TTL**: Sort by TTL value (click column header)
- **Content**: Sort by record content (click column header)

Click the column header to toggle between ascending and descending order.

### Filtering Records

To filter records:

1. Enter search text in the "Search" field above the records table
2. The table will filter in real-time to show only matching records
3. Filtering works across all fields (name, type, and content)
4. Use **Ctrl+F** to quickly focus the record filter field
5. Use **Escape** to clear the filter

The filter is case-insensitive and supports partial matching, making it easy to find records even in large zone files.

## Caching Behavior

The application uses a selective caching approach for optimal performance and responsiveness:

1. Zone lists are cached during synchronization (performed every 10 minutes by default)
2. Records for a zone are loaded and cached only when the zone is selected
3. When adding, modifying, or deleting records:
   - The application immediately updates the UI to reflect your changes
   - Changes are sent to the deSEC API in real-time
   - The zone's cache is invalidated to ensure fresh data on next access
4. If offline, the application will use cached records but editing is disabled

This selective caching approach ensures the application remains responsive even with many zones, while still providing offline access to previously viewed records.

For more comprehensive information about the caching system, please refer to the [CACHING.md](CACHING.md) document.

## Troubleshooting

### Common Error Messages

- **"Another RRset with the same subdomain and type exists"**: You cannot have multiple record sets with the same name and type. Edit the existing record instead.
- **"Ensure this value is less than or equal to 86400"**: TTL value exceeds the maximum allowed by deSEC.
- **"Ensure this value is greater than or equal to 3600"**: TTL value is below the minimum allowed by deSEC.

### API Errors

If you encounter API errors when managing records:

1. Check your internet connection
2. Verify your API token is valid
3. Ensure your record format meets deSEC requirements
4. Check the application logs for detailed error information

#### Common API Rate Limiting

The deSEC API enforces rate limiting that may occasionally trigger when performing rapid operations. The application handles these gracefully by:

1. Showing clear error messages when rate limiting occurs
2. Implementing configurable throttling for bulk operations
3. Providing detailed logs with request/response data for troubleshooting

If you frequently encounter rate limiting errors, consider increasing the throttle delay in the settings.
