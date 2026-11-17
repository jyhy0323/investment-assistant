document.addEventListener("DOMContentLoaded", () => {
  console.log("[PAGE]    페이지 로드 완료");

  const searchForm = document.getElementById("search-form");
  const codeInput = document.getElementById("stock-code");
  const fetchBtn = document.getElementById("fetch-btn");
  const exampleBtns = document.querySelectorAll(".example-btn");

  const statusMessage = document.getElementById("status-message");
  const errorBox = document.getElementById("error-box");
  const resultArea = document.getElementById("result-area");

  const stockNameEl = document.getElementById("stock-name");
  const stockCodeBadgeEl = document.getElementById("stock-code-badge");
  const currentPriceEl = document.getElementById("current-price");
  const changeRateEl = document.getElementById("change-rate");
  const marketCapEl = document.getElementById("market-cap");
  const perValueEl = document.getElementById("per-value");
  const pbrValueEl = document.getElementById("pbr-value");
  const financialsBodyEl = document.getElementById("financials-body");
  const newsListEl = document.getElementById("news-list");

  function showStatus(msg) {
    statusMessage.textContent = msg;
    statusMessage.classList.remove("hidden");
  }

  function hideStatus() {
    statusMessage.classList.add("hidden");
  }

  function showErrors(errors) {
    if (!errors || errors.length === 0) {
      errorBox.classList.add("hidden");
      errorBox.innerHTML = "";
      return;
    }
    errorBox.innerHTML = errors.map((err) => `<p>• ${escapeHtml(err)}</p>`).join("");
    errorBox.classList.remove("hidden");
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function formatNumber(num) {
    if (num === null || num === undefined || Number.isNaN(Number(num))) {
      return "-";
    }
    return Number(num).toLocaleString("ko-KR");
  }

  function formatKoreanWon(amount) {
    if (amount === null || amount === undefined || Number.isNaN(Number(amount))) {
      return "-";
    }
    const sign = amount < 0 ? "-" : "";
    const abs = Math.abs(Number(amount));
    const jo = Math.floor(abs / 1e12);
    const eok = Math.round((abs % 1e12) / 1e8);

    if (jo > 0) {
      return eok > 0
        ? `${sign}${jo.toLocaleString("ko-KR")}조 ${eok.toLocaleString("ko-KR")}억`
        : `${sign}${jo.toLocaleString("ko-KR")}조`;
    }
    if (eok > 0) {
      return `${sign}${eok.toLocaleString("ko-KR")}억`;
    }
    return `${sign}${abs.toLocaleString("ko-KR")}원`;
  }

  function renderSnapshot(data) {
    const snap = data.snapshot || {};
    stockNameEl.textContent = data.name || "알 수 없음";
    stockCodeBadgeEl.textContent = data.code || "-";

    currentPriceEl.textContent =
      snap.current_price !== null && snap.current_price !== undefined
        ? `${formatNumber(snap.current_price)}원`
        : "-";

    changeRateEl.className = "change-rate";
    if (snap.change_rate === null || snap.change_rate === undefined) {
      changeRateEl.textContent = "-";
      changeRateEl.classList.add("flat");
    } else if (snap.change_rate > 0) {
      changeRateEl.textContent = `+${snap.change_rate}% ▲`;
      changeRateEl.classList.add("up");
    } else if (snap.change_rate < 0) {
      changeRateEl.textContent = `${snap.change_rate}% ▼`;
      changeRateEl.classList.add("down");
    } else {
      changeRateEl.textContent = `0% -`;
      changeRateEl.classList.add("flat");
    }

    marketCapEl.textContent = formatKoreanWon(snap.market_cap);
    perValueEl.textContent = snap.per !== null && snap.per !== undefined ? `${snap.per}배` : "-";
    pbrValueEl.textContent = snap.pbr !== null && snap.pbr !== undefined ? `${snap.pbr}배` : "-";
  }

  function renderFinancials(financials) {
    financialsBodyEl.innerHTML = "";
    if (!financials || financials.length === 0) {
      financialsBodyEl.innerHTML = `<tr><td colspan="5" style="text-align:center;">표시할 실적 데이터가 없습니다.</td></tr>`;
      return;
    }

    financials.forEach((row) => {
      const tr = document.createElement("tr");
      if (row.is_consensus) {
        tr.classList.add("row-consensus");
      }

      const typeBadge = row.is_consensus
        ? `<span class="badge-consensus">추정 (E)</span>`
        : `<span class="badge-confirmed">확정</span>`;

      const roeText = row.roe !== null && row.roe !== undefined ? `${row.roe}%` : "-";

      tr.innerHTML = `
        <td>${escapeHtml(row.period)}</td>
        <td>${typeBadge}</td>
        <td>${escapeHtml(formatKoreanWon(row.revenue))}</td>
        <td>${escapeHtml(formatKoreanWon(row.operating_income))}</td>
        <td>${escapeHtml(roeText)}</td>
      `;
      financialsBodyEl.appendChild(tr);
    });
  }

  function renderNews(news) {
    newsListEl.innerHTML = "";
    if (!news || news.length === 0) {
      newsListEl.innerHTML = `<li class="news-item">수집된 관련 뉴스가 없습니다.</li>`;
      return;
    }

    news.forEach((item) => {
      const li = document.createElement("li");
      li.className = "news-item";
      const safeTitle = escapeHtml(item.title || "제목 없음");
      const safeUrl = item.url || "#";
      const safeDesc = item.description ? `<p class="news-desc">${escapeHtml(item.description)}</p>` : "";
      const safePub = escapeHtml(item.published || "");

      li.innerHTML = `
        <a class="news-title" href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">${safeTitle}</a>
        ${safeDesc}
        <span class="news-meta">${safePub}</span>
      `;
      newsListEl.appendChild(li);
    });
  }

  async function fetchStock(code) {
    const trimmed = code.trim();
    if (!/^\d{6}$/.test(trimmed)) {
      const msg = "종목코드는 6자리 숫자여야 합니다. (예: 000660)";
      console.error(`[ERROR]   수집 중 오류 발생 (${msg})`);
      showErrors([msg]);
      resultArea.classList.add("hidden");
      return;
    }

    console.log(`[SEARCH]  종목 수집 요청 시작 (${trimmed})`);
    showErrors([]);
    showStatus(`[${trimmed}] 네이버 금융 데이터 및 최신 뉴스를 수집하고 있습니다...`);
    fetchBtn.disabled = true;

    try {
      const response = await fetch("/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: trimmed }),
      });

      const data = await response.json();

      if (data.errors && data.errors.length > 0) {
        console.error(`[ERROR]   수집 중 오류 발생 (${data.errors.join(" / ")})`);
        showErrors(data.errors);
      }

      if (!response.ok && !data.name) {
        resultArea.classList.add("hidden");
        return;
      }

      const price = data.snapshot ? data.snapshot.current_price : "-";
      console.log(`[PARSED]  기본 정보 수집 완료 (${data.name}, ${price})`);
      console.log(`[NEWS]    뉴스 수집 완료 (${(data.news || []).length}건)`);

      renderSnapshot(data);
      renderFinancials(data.financials);
      renderNews(data.news);

      resultArea.classList.remove("hidden");
      console.log("[RENDER]  화면 데이터 카드 렌더링 완료");
    } catch (err) {
      const msg = "서버와 통신하는 중 오류가 발생했습니다.";
      console.error(`[ERROR]   수집 중 오류 발생 (${err.message})`);
      showErrors([msg]);
      resultArea.classList.add("hidden");
    } finally {
      hideStatus();
      fetchBtn.disabled = false;
    }
  }

  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    fetchStock(codeInput.value);
  });

  exampleBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const code = btn.dataset.code || "";
      codeInput.value = code;
      fetchStock(code);
    });
  });
});
