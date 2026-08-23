(() => {
  const browser = document.querySelector(".browser[data-history-url]");
  const search = document.querySelector("#search");
  const status = document.querySelector("#status-filter");
  const country = document.querySelector("#country-filter");
  const certificateType = document.querySelector("#type-filter");
  const body = document.querySelector("tbody");
  const count = document.querySelector("#visible-count");
  const empty = document.querySelector("#empty-state");
  const loadMore = document.querySelector("#load-more");

  if (!browser || !search || !status || !country || !certificateType || !body || !count || !empty || !loadMore) return;

  const pageSize = 200;
  const initialParams = new URLSearchParams(window.location.search);
  const requestedCountry = (initialParams.get("country") || "").toUpperCase();
  const requestedType = (initialParams.get("type") || "").toLowerCase();
  let records = [];
  let visibleLimit = pageSize;

  search.value = initialParams.get("search") || "";
  const requestedStatus = initialParams.get("status") === "removed"
    ? "archived"
    : initialParams.get("status");
  if (["active", "archived"].includes(requestedStatus)) status.value = requestedStatus;
  if (requestedType === "club") certificateType.value = "CLUB";
  if (["international", "intl"].includes(requestedType)) certificateType.value = "INTL";

  const parseCsv = (text) => {
    const table = [];
    let row = [];
    let field = "";
    let quoted = false;

    for (let index = 0; index < text.length; index += 1) {
      const character = text[index];
      if (quoted) {
        if (character === '"' && text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else if (character === '"') {
          quoted = false;
        } else {
          field += character;
        }
      } else if (character === '"') {
        quoted = true;
      } else if (character === ",") {
        row.push(field);
        field = "";
      } else if (character === "\n") {
        row.push(field);
        table.push(row);
        row = [];
        field = "";
      } else if (character !== "\r") {
        field += character;
      }
    }
    if (field || row.length) {
      row.push(field);
      table.push(row);
    }

    const [headers = [], ...values] = table;
    return values
      .filter((valuesRow) => valuesRow.some(Boolean))
      .map((valuesRow) => Object.fromEntries(
        headers.map((header, index) => [header, valuesRow[index] ?? ""]),
      ));
  };

  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  };

  const certificateTypeLabel = (value) => {
    if (value === "INTL") return "International";
    if (value === "CLUB") return "Club";
    return value || "—";
  };

  const renderRow = (record) => {
    const row = document.createElement("tr");

    const yacht = document.createElement("td");
    yacht.append(element("strong", record.yacht_name || "Unnamed yacht"));
    yacht.append(element("small", record.class));
    row.append(yacht);
    row.append(element("td", record.sail_no || "—"));
    row.append(element("td", record.country));
    row.append(element("td", certificateTypeLabel(record.certificate_type)));

    const issuedCell = document.createElement("td");
    const issued = element("time", record.issue_date.slice(0, 10) || "—");
    issued.dateTime = record.issue_date;
    issuedCell.append(issued);
    row.append(issuedCell);

    const statusCell = document.createElement("td");
    let label = "Archived";
    if (record.status === "active") label = "Active";
    else if (record.removed_on) label = `Archived on ${record.removed_on}`;
    statusCell.append(element("span", label, `status ${record.status}`));
    row.append(statusCell);

    const certificate = document.createElement("td");
    const link = element("a", "Open certificate", "certificate-link");
    link.href = record.certificate_url;
    link.target = "_blank";
    link.rel = "noopener";
    certificate.append(link, element("small", record.ref_no));
    const performance = element("a", "Performance guide", "performance-link");
    const performanceParams = new URLSearchParams({
      year: record.vpp_year,
      country: record.country,
      ref: record.ref_no,
    });
    performance.href = `../../performance/?${performanceParams}`;
    certificate.append(performance);
    row.append(certificate);
    return row;
  };

  const render = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const matches = records.filter((record) => {
      const searchable = [
        record.country,
        record.nat_auth,
        record.ref_no,
        record.sail_no,
        record.yacht_name,
        record.class,
        certificateTypeLabel(record.certificate_type),
      ].join(" ").toLocaleLowerCase();
      const matchesText = !query || searchable.includes(query);
      const matchesStatus = status.value === "all" || record.status === status.value;
      const matchesCountry = country.value === "all" || record.country === country.value;
      const matchesType = certificateType.value === "all" || record.certificate_type === certificateType.value;
      return matchesText && matchesStatus && matchesCountry && matchesType;
    });

    body.replaceChildren(...matches.slice(0, visibleLimit).map(renderRow));
    const shown = Math.min(matches.length, visibleLimit);
    count.textContent = `${shown.toLocaleString()} of ${matches.length.toLocaleString()} matching certificates shown`;
    empty.textContent = "No certificates match these filters.";
    empty.hidden = matches.length !== 0;
    loadMore.hidden = shown === matches.length;
  };

  const syncUrl = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("search");
    url.searchParams.delete("country");
    url.searchParams.delete("status");
    url.searchParams.delete("type");

    const query = search.value.trim();
    if (query) url.searchParams.set("search", query);
    if (country.value !== "all") url.searchParams.set("country", country.value);
    if (status.value !== "all") url.searchParams.set("status", status.value);
    if (certificateType.value === "CLUB") url.searchParams.set("type", "club");
    if (certificateType.value === "INTL") url.searchParams.set("type", "international");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  };

  const resetAndRender = () => {
    visibleLimit = pageSize;
    syncUrl();
    render();
  };

  search.addEventListener("input", resetAndRender);
  status.addEventListener("change", resetAndRender);
  country.addEventListener("change", resetAndRender);
  certificateType.addEventListener("change", resetAndRender);
  loadMore.addEventListener("click", () => {
    visibleLimit += pageSize;
    render();
  });

  fetch(browser.dataset.historyUrl)
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.text();
    })
    .then((text) => {
      records = parseCsv(text).map((record) => (
        record.status === "removed" ? {...record, status: "archived"} : record
      )).sort((left, right) => (
        right.issue_date.localeCompare(left.issue_date)
        || left.country.localeCompare(right.country)
        || left.yacht_name.localeCompare(right.yacht_name)
        || left.ref_no.localeCompare(right.ref_no)
      ));
      const countries = [...new Set(records.map((record) => record.country))]
        .filter(Boolean)
        .sort((left, right) => left.localeCompare(right));
      for (const countryCode of countries) {
        const option = element("option", countryCode);
        option.value = countryCode;
        country.append(option);
      }
      if (countries.includes(requestedCountry)) country.value = requestedCountry;
      syncUrl();
      render();
    })
    .catch((error) => {
      count.textContent = "Certificate history unavailable";
      empty.textContent = `Could not load certificates.csv (${error.message}).`;
      empty.hidden = false;
    });
})();
