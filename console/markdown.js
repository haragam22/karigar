// Small renderer for the engine's Markdown job cards. Raw HTML is always escaped.
const escape = (value) =>
  value.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export function renderDocument(text) {
  const lines = text.split("\n");
  const out = [];
  let table = false,
    list = false;
  const close = () => {
    if (table) {
      out.push("</tbody></table></div>");
      table = false;
    }
    if (list) {
      out.push("</ul>");
      list = false;
    }
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (line.startsWith("|") && line.endsWith("|")) {
      if (/^\|[\s:|\-]+\|$/.test(line)) continue;
      if (!table) {
        if (list) {
          out.push("</ul>");
          list = false;
        }
        out.push('<div class="table-wrap"><table><tbody>');
        table = true;
      }
      out.push(
        "<tr>" +
          line
            .slice(1, -1)
            .split("|")
            .map((cell) => `<td>${escape(cell.trim())}</td>`)
            .join("") +
          "</tr>",
      );
      continue;
    }
    if (table) {
      out.push("</tbody></table></div>");
      table = false;
    }
    if (line.startsWith("- ")) {
      if (!list) {
        out.push("<ul>");
        list = true;
      }
      out.push(`<li>${escape(line.slice(2))}</li>`);
      continue;
    }
    if (list) {
      out.push("</ul>");
      list = false;
    }
    if (!line || line.startsWith("![")) continue;
    const heading = /^(#{1,6})\s+(.*)/.exec(line);
    if (heading) {
      out.push(
        `<h${Math.min(heading[1].length + 1, 6)}>${escape(heading[2])}</h${Math.min(heading[1].length + 1, 6)}>`,
      );
      continue;
    }
    out.push(
      `<p>${escape(line).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")}</p>`,
    );
  }
  close();
  return out.join("");
}
