document.addEventListener("DOMContentLoaded", () => {
  console.log("[PAGE]      페이지 로드 완료 (모드: main)");

  let currentTab = "fundamental"; // 'fundamental' | 'technical' | 'rebalance'
  const state = {
    fundamental: { code: "", data: null, conversationId: "" },
    technical: { code: "", data: null, conversationId: "" },
    rebalance: { code: "PORTFOLIO", data: null, conversationId: "" },
  };

  // 테마(다크/라이트모드) 초기화 및 전환
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const THEME_STORAGE_KEY = "investment_assistant_theme";
  const applyTheme = (theme) => {
    document.documentElement.setAttribute("data-theme", theme);
    if (themeToggleBtn) {
      themeToggleBtn.textContent = theme === "dark" ? "☀️ 라이트모드" : "🌙 다크모드";
    }
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (_) {}
  };
  const savedTheme = (() => {
    try {
      return localStorage.getItem(THEME_STORAGE_KEY) || "light";
    } catch (_) {
      return "light";
    }
  })();
  applyTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      if (state.fundamental.data) drawForeignDonut((state.fundamental.data.snapshot || {}).foreign_rate);
      if (state.technical.data) {
        drawRsiDonut((state.technical.data.price_summary || {}).rsi_14);
        drawTechChart(activeChartSeries);
      }
      if (state.rebalance.data) renderRebalanceDonuts(state.rebalance.data);
    });
  }

  // 공통 요소
  const tabBtns = document.querySelectorAll(".tab-btn");
  const searchSectionEl = document.getElementById("search-section");
  const searchForm = document.getElementById("search-form");
  const codeInput = document.getElementById("stock-code");
  const analyzeBtn = document.getElementById("analyze-btn");
  const exampleBtns = document.querySelectorAll("#search-section .example-btn");
  const statusMessage = document.getElementById("status-message");
  const errorBox = document.getElementById("error-box");

  // 패널 요소
  const panelFundamental = document.getElementById("panel-fundamental");
  const panelTechnical = document.getElementById("panel-technical");
  const panelRebalance = document.getElementById("panel-rebalance");

  // 추천 질문 영역
  const fundQuickQuestionsEl = document.getElementById("fund-quick-questions");
  const techQuickQuestionsEl = document.getElementById("tech-quick-questions");
  const rebalQuickQuestionsEl = document.getElementById("rebal-quick-questions");

  // [탭 3] 리밸런싱 도우미 요소
  const rebalRowsEl = document.getElementById("rebal-rows");
  const rebalAddRowBtn = document.getElementById("rebal-add-row-btn");
  const rebalSampleBtn = document.getElementById("rebal-sample-btn");
  const rebalCashInput = document.getElementById("rebal-cash-input");
  const rebalCashTargetInput = document.getElementById("rebal-cash-target");
  const rebalCalcBtn = document.getElementById("rebal-calc-btn");
  const rebalTargetSumHintEl = document.getElementById("rebal-target-sum-hint");
  const rebalanceResultEl = document.getElementById("rebalance-result");
  const rebalWarningsEl = document.getElementById("rebal-warnings");
  const rebalTotalBadgeEl = document.getElementById("rebal-total-badge");
  const rebalCurrentDonutEl = document.getElementById("rebal-current-donut");
  const rebalTargetDonutEl = document.getElementById("rebal-target-donut");
  const rebalLegendEl = document.getElementById("rebal-legend");
  const rebalTableBodyEl = document.getElementById("rebal-table-body");
  const rebalAiBtn = document.getElementById("rebal-ai-btn");
  const rebalAiAnswerEl = document.getElementById("rebal-ai-answer");
  const rebalChatForm = document.getElementById("rebal-chat-form");
  const rebalFollowupInput = document.getElementById("rebal-followup-input");

  // [탭 1] 투자종목분석 요소
  const fundAiAnswerEl = document.getElementById("fund-ai-answer");
  const fundChatForm = document.getElementById("fund-chat-form");
  const fundFollowupInput = document.getElementById("fund-followup-input");
  const stockNameEl = document.getElementById("stock-name");
  const stockCodeBadgeEl = document.getElementById("stock-code-badge");
  const currentPriceEl = document.getElementById("current-price");
  const changeRateEl = document.getElementById("change-rate");
  const marketCapEl = document.getElementById("market-cap");
  const perValueEl = document.getElementById("per-value");
  const pbrValueEl = document.getElementById("pbr-value");
  const financialsBodyEl = document.getElementById("financials-body");
  const dartListEl = document.getElementById("dart-list");
  const newsListEl = document.getElementById("news-list");
  const foreignDonutEl = document.getElementById("foreign-donut-chart");
  const foreignPctTextEl = document.getElementById("foreign-pct-text");
  const domesticPctTextEl = document.getElementById("domestic-pct-text");
  const frChangeBadgeEl = document.getElementById("fr-change-badge");
  const signalPositiveListEl = document.getElementById("signal-positive-list");
  const signalNegativeListEl = document.getElementById("signal-negative-list");
  const supplyBars5dEl = document.getElementById("supply-bars-5d");
  const supplyBars20dEl = document.getElementById("supply-bars-20d");
  const supplyDailyBodyEl = document.getElementById("supply-daily-body");

  // [탭 2] 지표해석기 요소
  const techAiAnswerEl = document.getElementById("tech-ai-answer");
  const techChatForm = document.getElementById("tech-chat-form");
  const techFollowupInput = document.getElementById("tech-followup-input");
  const techAsOfEl = document.getElementById("tech-as-of");
  const techCloseEl = document.getElementById("tech-close");
  const techVolumeEl = document.getElementById("tech-volume");
  const techRsiEl = document.getElementById("tech-rsi");
  const techMa5El = document.getElementById("tech-ma5");
  const techMa20El = document.getElementById("tech-ma20");
  const techMa60El = document.getElementById("tech-ma60");
  const techHigh20El = document.getElementById("tech-high20");
  const techLow20El = document.getElementById("tech-low20");
  const candlesBodyEl = document.getElementById("candles-body");
  const techChartEl = document.getElementById("tech-chart");
  const chartTooltipEl = document.getElementById("chart-tooltip");
  const rsiDonutEl = document.getElementById("rsi-donut-chart");
  const rsiStatusBadgeEl = document.getElementById("rsi-status-badge");
  const rsiDescEl = document.getElementById("rsi-desc");
  let activeChartSeries = [];
  let activeChartCurrency = "KRW";
  let activeSupportResistance = null;

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

  function renderMarkdownSafe(rawText) {
    const safe = escapeHtml(rawText || "");
    const lines = safe.split(/\r?\n/);
    let html = "";
    let inList = false;

    const formatInline = (line) =>
      line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        continue;
      }

      if (line === "---" || line === "***") {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        html += "<hr/>";
      } else if (line.startsWith("#### ")) {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        html += `<h4>${formatInline(line.slice(5))}</h4>`;
      } else if (line.startsWith("### ")) {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        html += `<h3>${formatInline(line.slice(4))}</h3>`;
      } else if (line.startsWith("&gt; ")) {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        html += `<blockquote>${formatInline(line.slice(5))}</blockquote>`;
      } else if (line.startsWith("* ") || line.startsWith("- ")) {
        if (!inList) {
          html += "<ul>";
          inList = true;
        }
        html += `<li>${formatInline(line.slice(2))}</li>`;
      } else {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        html += `<p>${formatInline(line)}</p>`;
      }
    }
    if (inList) html += "</ul>";
    return html;
  }

  function appendChatBubble(threadEl, role, text) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;
    if (role === "user") {
      bubble.textContent = text;
    } else {
      bubble.innerHTML = renderMarkdownSafe(text);
    }
    threadEl.appendChild(bubble);
    threadEl.scrollTop = threadEl.scrollHeight;
    return bubble;
  }

  function formatNumber(num) {
    if (num === null || num === undefined || Number.isNaN(Number(num))) {
      return "-";
    }
    return Number(num).toLocaleString("ko-KR");
  }

  function formatPrice(num, currency = "KRW") {
    if (num === null || num === undefined || Number.isNaN(Number(num))) {
      return "-";
    }
    if (currency === "USD") {
      return `$${Number(num).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `${Number(num).toLocaleString("ko-KR")}원`;
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

  function drawForeignDonut(rate) {
    if (!foreignDonutEl) return;
    const size = 140;
    const dpr = window.devicePixelRatio || 1;
    foreignDonutEl.width = size * dpr;
    foreignDonutEl.height = size * dpr;

    const ctx = foreignDonutEl.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    const cx = size / 2;
    const cy = size / 2;
    const radius = 54;
    const lineWidth = 18;
    const hasVal = rate != null && !Number.isNaN(Number(rate));
    const clamped = hasVal ? Math.max(0, Math.min(100, Number(rate))) : 0;

    // 배경 링 (국내·기타)
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = lineWidth;
    ctx.stroke();

    // 외국인 보유 비율 링
    if (hasVal && clamped > 0) {
      const startAngle = -Math.PI / 2;
      const endAngle = startAngle + (clamped / 100) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, startAngle, endAngle);
      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = lineWidth;
      ctx.lineCap = "round";
      ctx.stroke();
    }

    // 중앙 텍스트
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = (document.documentElement.getAttribute("data-theme") === "dark" ? "#f2f4f6" : "#191f28");
    ctx.font = "bold 18px sans-serif";
    ctx.fillText(hasVal ? `${clamped.toFixed(1)}%` : "-", cx, cy - 6);
    ctx.fillStyle = "#64748b";
    ctx.font = "11px sans-serif";
    ctx.fillText("외국인", cx, cy + 14);

    if (foreignPctTextEl && domesticPctTextEl) {
      foreignPctTextEl.textContent = hasVal ? `${clamped.toFixed(2)}%` : "-";
      domesticPctTextEl.textContent = hasVal ? `${(100 - clamped).toFixed(2)}%` : "-";
    }
  }

  function drawRsiDonut(rsi) {
    if (!rsiDonutEl) return;
    const size = 140;
    const dpr = window.devicePixelRatio || 1;
    rsiDonutEl.width = size * dpr;
    rsiDonutEl.height = size * dpr;

    const ctx = rsiDonutEl.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    const cx = size / 2;
    const cy = size / 2;
    const radius = 54;
    const lineWidth = 18;
    const hasVal = rsi != null && !Number.isNaN(Number(rsi));
    const clamped = hasVal ? Math.max(0, Math.min(100, Number(rsi))) : 0;

    // 3구간 배경 가이드 링 (연한 색: 0~30 과매도, 30~70 중립, 70~100 과매수)
    const startBase = -Math.PI / 2;
    const zones = [
      [0, 30, "#dbeafe"],
      [30, 70, "#e2e8f0"],
      [70, 100, "#fee2e2"],
    ];
    zones.forEach(([from, to, color]) => {
      ctx.beginPath();
      ctx.arc(
        cx,
        cy,
        radius,
        startBase + (from / 100) * Math.PI * 2,
        startBase + (to / 100) * Math.PI * 2
      );
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    });

    // 현재 RSI 색상 및 상태 판정
    let activeColor = "#64748b";
    let statusText = "중립 구간";
    let badgeClass = "neutral";
    let descText = "현재 과열도 침체도 아닌 중립적인 매매 심리 구간입니다.";

    if (!hasVal) {
      statusText = "-";
      descText = "RSI(14) 데이터가 없습니다.";
    } else if (clamped <= 30) {
      activeColor = "#2563eb";
      statusText = "과매도 (침체)";
      badgeClass = "oversold";
      descText = "단기 낙폭이 커서 매도세가 과하게 몰린 과매도 구간입니다.";
    } else if (clamped >= 70) {
      activeColor = "#dc2626";
      statusText = "과매수 (과열)";
      badgeClass = "overbought";
      descText = "단기 매수세가 강하게 몰려 과열(차익실현 주의) 구간입니다.";
    } else if (clamped <= 40) {
      activeColor = "#3b82f6";
      statusText = "중립 (약세권)";
      badgeClass = "oversold";
      descText = "과매도(30)에 근접한 약세 구간으로 반등 여부를 지켜볼 자리입니다.";
    } else if (clamped >= 60) {
      activeColor = "#f97316";
      statusText = "중립 (강세권)";
      badgeClass = "overbought";
      descText = "매수 심리가 우세한 강세 구간으로 과매수(70) 진입 여부를 체크하세요.";
    }

    // 현재 RSI 값 채우기 아크
    if (hasVal && clamped > 0) {
      ctx.beginPath();
      ctx.arc(cx, cy, radius, startBase, startBase + (clamped / 100) * Math.PI * 2);
      ctx.strokeStyle = activeColor;
      ctx.lineWidth = lineWidth;
      ctx.lineCap = "round";
      ctx.stroke();
    }

    // 중앙 텍스트
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = (document.documentElement.getAttribute("data-theme") === "dark" ? "#f2f4f6" : "#191f28");
    ctx.font = "bold 19px sans-serif";
    ctx.fillText(hasVal ? clamped.toFixed(1) : "-", cx, cy - 6);
    ctx.fillStyle = "#64748b";
    ctx.font = "11px sans-serif";
    ctx.fillText("RSI (14)", cx, cy + 14);

    if (rsiStatusBadgeEl) {
      rsiStatusBadgeEl.textContent = statusText;
      rsiStatusBadgeEl.className = `rsi-badge ${badgeClass}`;
    }
    if (rsiDescEl) {
      rsiDescEl.textContent = descText;
    }
  }

  function switchTab(nextTab) {
    currentTab = nextTab;
    console.log(`[TAB]       탭 전환 (${currentTab})`);

    tabBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === currentTab);
    });

    showErrors([]);
    panelFundamental.classList.add("hidden");
    panelTechnical.classList.add("hidden");
    if (panelRebalance) panelRebalance.classList.add("hidden");

    if (currentTab === "rebalance") {
      if (searchSectionEl) searchSectionEl.classList.add("hidden");
      if (panelRebalance) panelRebalance.classList.remove("hidden");
      if (state.rebalance.data) {
        renderRebalanceDonuts(state.rebalance.data);
      }
    } else if (currentTab === "fundamental") {
      if (searchSectionEl) searchSectionEl.classList.remove("hidden");
      if (state.fundamental.data) {
        panelFundamental.classList.remove("hidden");
        drawForeignDonut((state.fundamental.data.snapshot || {}).foreign_rate);
      }
    } else {
      if (searchSectionEl) searchSectionEl.classList.remove("hidden");
      if (state.technical.data) {
        panelTechnical.classList.remove("hidden");
        drawRsiDonut((state.technical.data.price_summary || {}).rsi_14);
        drawTechChart(activeChartSeries);
      }
    }
  }

  function renderFundamental(data) {
    const snap = data.snapshot || {};
    const isEtf = data.asset_type === "etf";
    const isUs = data.market === "US";
    const currency = data.currency || (isUs ? "USD" : "KRW");

    stockNameEl.textContent = data.name || "알 수 없음";
    if (isUs) {
      stockCodeBadgeEl.textContent = `${data.code || "-"} · ${data.exchange || "US"}`;
    } else {
      stockCodeBadgeEl.textContent = isEtf ? `${data.code || "-"} · ETF` : (data.code || "-");
    }
    currentPriceEl.textContent = formatPrice(snap.current_price, currency);

    changeRateEl.className = "change-rate";
    if (snap.change_rate == null) {
      changeRateEl.textContent = "-";
      changeRateEl.classList.add("flat");
    } else if (snap.change_rate > 0) {
      changeRateEl.textContent = `+${snap.change_rate}% ▲`;
      changeRateEl.classList.add("up");
    } else if (snap.change_rate < 0) {
      changeRateEl.textContent = `${snap.change_rate}% ▼`;
      changeRateEl.classList.add("down");
    } else {
      changeRateEl.textContent = "0% -";
      changeRateEl.classList.add("flat");
    }

    const stockMetricsGridEl = document.getElementById("stock-metrics-grid");
    const etfInfoGridEl = document.getElementById("etf-info-grid");
    const foreignDonutSecEl = document.getElementById("foreign-donut-section");
    const supplyCardEl = document.getElementById("supply-demand-card");
    const financialsCardEl = document.getElementById("financials-card");
    const dartCardEl = document.getElementById("dart-card");

    if (isUs) {
      if (stockMetricsGridEl) stockMetricsGridEl.classList.remove("hidden");
      if (etfInfoGridEl) etfInfoGridEl.classList.add("hidden");
      if (foreignDonutSecEl) foreignDonutSecEl.classList.add("hidden");
      if (supplyCardEl) supplyCardEl.classList.add("hidden");
      if (financialsCardEl) financialsCardEl.classList.add("hidden");
      if (dartCardEl) dartCardEl.classList.add("hidden");

      marketCapEl.textContent = snap.market_cap_text || "-";
      perValueEl.textContent = snap.per != null ? `${snap.per}배` : "-";
      pbrValueEl.textContent = snap.pbr != null ? `${snap.pbr}배` : "-";
    } else if (isEtf) {
      if (stockMetricsGridEl) stockMetricsGridEl.classList.add("hidden");
      if (foreignDonutSecEl) foreignDonutSecEl.classList.add("hidden");
      if (supplyCardEl) supplyCardEl.classList.remove("hidden");
      if (financialsCardEl) financialsCardEl.classList.add("hidden");
      if (dartCardEl) dartCardEl.classList.add("hidden");
      if (etfInfoGridEl) etfInfoGridEl.classList.remove("hidden");

      const etf = data.etf_info || {};
      const setTxt = (id, txt) => {
        const el = document.getElementById(id);
        if (el) el.textContent = txt;
      };
      setTxt("etf-issuer", etf.issuer || "-");
      setTxt("etf-base-index", etf.base_index || "-");
      setTxt("etf-market-cap", etf.total_nav && etf.total_nav !== "-" ? etf.total_nav : formatKoreanWon(snap.market_cap));
      setTxt("etf-fee", etf.total_fee || "-");
      setTxt("etf-nav", etf.nav != null ? `${formatNumber(Math.round(etf.nav))}원` : "-");
      setTxt("etf-div-yield", etf.dividend_yield != null ? `${etf.dividend_yield}%` : "-");
    } else {
      if (stockMetricsGridEl) stockMetricsGridEl.classList.remove("hidden");
      if (foreignDonutSecEl) foreignDonutSecEl.classList.remove("hidden");
      if (supplyCardEl) supplyCardEl.classList.remove("hidden");
      if (financialsCardEl) financialsCardEl.classList.remove("hidden");
      if (dartCardEl) dartCardEl.classList.remove("hidden");
      if (etfInfoGridEl) etfInfoGridEl.classList.add("hidden");

      marketCapEl.textContent = formatKoreanWon(snap.market_cap);
      perValueEl.textContent = snap.per != null ? `${snap.per}배` : "-";
      pbrValueEl.textContent = snap.pbr != null ? `${snap.pbr}배` : "-";
    }

    financialsBodyEl.innerHTML = "";
    const financials = data.financials || [];
    if (financials.length === 0) {
      financialsBodyEl.innerHTML = `<tr><td colspan="5" style="text-align:center;">표시할 실적 데이터가 없습니다.</td></tr>`;
    } else {
      financials.forEach((row) => {
        const tr = document.createElement("tr");
        if (row.is_consensus) tr.classList.add("row-consensus");
        const typeBadge = row.is_consensus
          ? `<span class="badge-consensus">추정 (E)</span>`
          : `<span class="badge-confirmed">확정</span>`;
        const roeText = row.roe != null ? `${row.roe}%` : "-";
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

    newsListEl.innerHTML = "";
    const news = data.news || [];
    if (news.length === 0) {
      newsListEl.innerHTML = `<li class="news-item">수집된 관련 뉴스가 없습니다.</li>`;
    } else {
      news.forEach((item) => {
        const li = document.createElement("li");
        li.className = "news-item";
        const safeDesc = item.description ? `<p class="news-desc">${escapeHtml(item.description)}</p>` : "";
        li.innerHTML = `
          <a class="news-title" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || "제목 없음")}</a>
          ${safeDesc}
          <span class="news-meta">${escapeHtml(item.published || "")}</span>
        `;
        newsListEl.appendChild(li);
      });
    }

    renderSupplyDemand(data.supply_demand);
    renderDisclosures(data.disclosures);

    const shortLinkEl = document.getElementById("short-trade-link");
    if (shortLinkEl && data.code) {
      shortLinkEl.href = `https://finance.naver.com/item/short_trade.naver?code=${encodeURIComponent(data.code)}`;
    }
  }

  function renderDisclosures(disclosures) {
    if (!dartListEl) return;
    dartListEl.innerHTML = "";
    const list = disclosures || [];
    if (list.length === 0) {
      dartListEl.innerHTML = `<li class="news-item">최근 3개월간 조회된 DART 공식 공시가 없습니다.</li>`;
      return;
    }

    list.forEach((item) => {
      const li = document.createElement("li");
      li.className = "news-item";
      const tagClass = item.tag === "positive" ? "positive" : item.tag === "negative" ? "negative" : "info";
      li.innerHTML = `
        <div class="dart-item-top">
          <span class="dart-badge ${tagClass}">${escapeHtml(item.tag_label || "일반 공시")}</span>
          <a class="news-title" style="margin-bottom:0;" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
        </div>
        <span class="news-meta">${escapeHtml(item.date)} · 제출인: ${escapeHtml(item.submitter || "-")}</span>
      `;
      dartListEl.appendChild(li);
    });
  }

  function formatSignedQty(num) {
    if (num === null || num === undefined || Number.isNaN(Number(num))) return "-";
    const n = Number(num);
    if (n > 0) return `+${n.toLocaleString("ko-KR")}`;
    return n.toLocaleString("ko-KR");
  }

  function qtyClass(num) {
    if (num > 0) return "net-buy";
    if (num < 0) return "net-sell";
    return "net-flat";
  }

  function renderSupplyBars(containerEl, periodData) {
    if (!containerEl) return;
    const rows = [
      { label: "외국인", val: periodData ? periodData.foreigner : 0 },
      { label: "기관", val: periodData ? periodData.organ : 0 },
      { label: "개인", val: periodData ? periodData.individual : 0 },
    ];
    const maxAbs = Math.max(...rows.map((r) => Math.abs(r.val || 0)), 1);

    containerEl.innerHTML = rows
      .map((r) => {
        const pct = Math.min(100, Math.round((Math.abs(r.val || 0) / maxAbs) * 100));
        const fillClass = r.val >= 0 ? "buy" : "sell";
        const textClass = qtyClass(r.val);
        return `
          <div class="supply-bar-row">
            <div class="supply-bar-header">
              <span>${r.label}</span>
              <span class="${textClass}">${escapeHtml(formatSignedQty(r.val))}주</span>
            </div>
            <div class="supply-bar-track">
              <div class="supply-bar-fill ${fillClass}" style="width: ${pct}%"></div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function renderSupplyDemand(sd) {
    if (!sd || !sd.days_5) {
      if (frChangeBadgeEl) frChangeBadgeEl.textContent = "20일 외인지분 변화: -";
      if (signalPositiveListEl) signalPositiveListEl.innerHTML = "<li>수급 데이터가 없습니다.</li>";
      if (signalNegativeListEl) signalNegativeListEl.innerHTML = "<li>수급 데이터가 없습니다.</li>";
      if (supplyBars5dEl) supplyBars5dEl.innerHTML = "";
      if (supplyBars20dEl) supplyBars20dEl.innerHTML = "";
      if (supplyDailyBodyEl) {
        supplyDailyBodyEl.innerHTML = `<tr><td colspan="5" style="text-align:center;">수급 데이터가 없습니다.</td></tr>`;
      }
      return;
    }

    if (frChangeBadgeEl) {
      const diff = sd.foreign_ratio_change_20d;
      if (diff == null) {
        frChangeBadgeEl.textContent = "20일 외인지분 변화: -";
      } else {
        const sign = diff > 0 ? "+" : "";
        frChangeBadgeEl.textContent = `20일 외인지분 변화: ${sign}${diff.toFixed(2)}%p`;
      }
    }

    const posList = (sd.signals && sd.signals.positive) || [];
    const negList = (sd.signals && sd.signals.negative) || [];
    if (signalPositiveListEl) {
      signalPositiveListEl.innerHTML = posList.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
    }
    if (signalNegativeListEl) {
      signalNegativeListEl.innerHTML = negList.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
    }

    renderSupplyBars(supplyBars5dEl, sd.days_5);
    renderSupplyBars(supplyBars20dEl, sd.days_20);

    if (supplyDailyBodyEl) {
      const daily = sd.daily || [];
      if (daily.length === 0) {
        supplyDailyBodyEl.innerHTML = `<tr><td colspan="5" style="text-align:center;">일별 수급 데이터가 없습니다.</td></tr>`;
      } else {
        supplyDailyBodyEl.innerHTML = daily
          .map((row) => {
            const frText = row.foreign_ratio != null ? `${row.foreign_ratio.toFixed(2)}%` : "-";
            return `
              <tr>
                <td>${escapeHtml(row.date)}</td>
                <td class="${qtyClass(row.foreigner_net)}">${escapeHtml(formatSignedQty(row.foreigner_net))}</td>
                <td class="${qtyClass(row.organ_net)}">${escapeHtml(formatSignedQty(row.organ_net))}</td>
                <td class="${qtyClass(row.individual_net)}">${escapeHtml(formatSignedQty(row.individual_net))}</td>
                <td>${escapeHtml(frText)}</td>
              </tr>
            `;
          })
          .join("");
      }
    }
  }

  function renderTechnical(data) {
    const summary = data.price_summary || {};
    const returns = data.period_returns || {};
    techAsOfEl.textContent = `기준일: ${data.as_of || "-"}`;

    [
      ["ret-1w", returns["1w"]],
      ["ret-1m", returns["1m"]],
      ["ret-3m", returns["3m"]],
      ["ret-6m", returns["6m"]],
    ].forEach(([elId, val]) => {
      const el = document.getElementById(elId);
      if (!el) return;
      el.className = "return-kpi-val";
      if (val == null || Number.isNaN(Number(val))) {
        el.textContent = "-";
        el.classList.add("net-flat");
      } else if (val > 0) {
        el.textContent = `+${val.toFixed(2)}%`;
        el.classList.add("net-buy");
      } else if (val < 0) {
        el.textContent = `${val.toFixed(2)}%`;
        el.classList.add("net-sell");
      } else {
        el.textContent = "0.00%";
        el.classList.add("net-flat");
      }
    });

    const cur = data.currency || (data.market === "US" ? "USD" : "KRW");
    activeChartCurrency = cur;

    techCloseEl.textContent = formatPrice(summary.latest_close, cur);
    techVolumeEl.textContent = summary.volume != null ? `${formatNumber(summary.volume)}주` : "-";
    techRsiEl.textContent = summary.rsi_14 != null ? `${summary.rsi_14}` : "-";
    techMa5El.textContent = formatPrice(summary.ma5, cur);
    techMa20El.textContent = formatPrice(summary.ma20, cur);
    techMa60El.textContent = formatPrice(summary.ma60, cur);
    techHigh20El.textContent = formatPrice(summary.high_20d, cur);
    techLow20El.textContent = formatPrice(summary.low_20d, cur);

    candlesBodyEl.innerHTML = "";
    const candles = [...(data.recent_candles || [])].reverse();
    if (candles.length === 0) {
      candlesBodyEl.innerHTML = `<tr><td colspan="6" style="text-align:center;">일봉 데이터가 없습니다.</td></tr>`;
    } else {
      candles.forEach((c) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${escapeHtml(c.date)}</td>
          <td>${escapeHtml(formatPrice(c.open, cur))}</td>
          <td>${escapeHtml(formatPrice(c.high, cur))}</td>
          <td>${escapeHtml(formatPrice(c.low, cur))}</td>
          <td><strong>${escapeHtml(formatPrice(c.close, cur))}</strong></td>
          <td>${escapeHtml(formatNumber(c.volume))}</td>
        `;
        candlesBodyEl.appendChild(tr);
      });
    }

    activeChartSeries = data.chart_series || [];
    activeSupportResistance = data.support_resistance || null;

    // 지지선·저항선 돌파/이탈 시나리오 렌더링
    const srSectionEl = document.getElementById("sr-section");
    if (srSectionEl && activeSupportResistance && activeSupportResistance.resistance_1 != null) {
      srSectionEl.classList.remove("hidden");
      const posEl = document.getElementById("sr-position-label");
      const resValEl = document.getElementById("sr-resistance-val");
      const supValEl = document.getElementById("sr-support-val");
      const resReasonEl = document.getElementById("sr-resistance-reason");
      const supReasonEl = document.getElementById("sr-support-reason");
      const bullMsgEl = document.getElementById("sr-bullish-msg");
      const bearMsgEl = document.getElementById("sr-bearish-msg");

      const toR = activeSupportResistance.to_resistance_pct;
      const toS = activeSupportResistance.to_support_pct;
      if (posEl) posEl.textContent = activeSupportResistance.position_label || "-";
      if (resValEl) {
        resValEl.textContent = `${formatPrice(activeSupportResistance.resistance_1, cur)}` +
          (toR != null ? ` (${toR >= 0 ? "+" : ""}${toR}%)` : "");
      }
      if (supValEl) {
        supValEl.textContent = `${formatPrice(activeSupportResistance.support_1, cur)}` +
          (toS != null ? ` (-${toS}%)` : "");
      }
      if (resReasonEl) resReasonEl.textContent = `📌 근거: ${activeSupportResistance.resistance_reason || "-"}`;
      if (supReasonEl) supReasonEl.textContent = `📌 근거: ${activeSupportResistance.support_reason || "-"}`;
      if (bullMsgEl) bullMsgEl.textContent = activeSupportResistance.bullish_trigger || "-";
      if (bearMsgEl) bearMsgEl.textContent = activeSupportResistance.bearish_trigger || "-";
    } else if (srSectionEl) {
      srSectionEl.classList.add("hidden");
    }
  }

  function drawTechChart(series, hoverIdx = -1) {
    if (!techChartEl || !series || series.length === 0) return;

    const width = techChartEl.parentElement.clientWidth;
    const height = techChartEl.parentElement.clientHeight;
    if (width <= 0 || height <= 0) return;

    const dpr = window.devicePixelRatio || 1;
    techChartEl.width = width * dpr;
    techChartEl.height = height * dpr;

    const ctx = techChartEl.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const pad = { top: 22, right: 18, bottom: 28, left: 74 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    // 최소/최대 가격 범위 계산 (지지선·저항선 포함)
    const values = [];
    series.forEach((item) => {
      ["close", "ma5", "ma20", "ma60"].forEach((k) => {
        if (item[k] != null) values.push(item[k]);
      });
    });
    if (activeSupportResistance) {
      if (activeSupportResistance.resistance_1 != null) values.push(activeSupportResistance.resistance_1);
      if (activeSupportResistance.support_1 != null) values.push(activeSupportResistance.support_1);
    }
    if (values.length === 0) return;

    let minVal = Math.min(...values);
    let maxVal = Math.max(...values);
    const span = maxVal - minVal || 1;
    minVal = minVal - span * 0.08;
    maxVal = maxVal + span * 0.08;

    const getX = (idx) => pad.left + (series.length === 1 ? plotW / 2 : (idx / (series.length - 1)) * plotW);
    const getY = (val) => pad.top + ((maxVal - val) / (maxVal - minVal)) * plotH;

    // 가로 눈금선 및 Y축 가격 레이블 (5줄)
    const isDarkTheme = document.documentElement.getAttribute("data-theme") === "dark";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const ratio = i / 4;
      const y = pad.top + ratio * plotH;
      const priceVal = maxVal - ratio * (maxVal - minVal);

      ctx.strokeStyle = isDarkTheme ? "#2c2e38" : "#e5e8eb";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();

      ctx.fillStyle = "#8b95a1";
      const yLabel = activeChartCurrency === "USD" ? `$${priceVal.toFixed(1)}` : formatNumber(Math.round(priceVal));
      ctx.fillText(yLabel, pad.left - 8, y);
    }

    // 저항선 / 지지선 수평 점선 + 우측 라벨 배지 그리기
    const drawHorizontalLevel = (val, label, lineColor, bgColor) => {
      if (val == null) return;
      const y = getY(val);
      ctx.save();
      ctx.strokeStyle = lineColor;
      ctx.lineWidth = 1.6;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
      ctx.setLineDash([]);

      const text = `${label} ${formatPrice(val, activeChartCurrency)}`;
      ctx.font = "bold 10.5px sans-serif";
      const textW = ctx.measureText(text).width;
      const boxW = textW + 12;
      const boxH = 18;
      const boxX = width - pad.right - boxW;
      const boxY = Math.max(4, Math.min(y - boxH / 2, height - pad.bottom - boxH));

      ctx.fillStyle = bgColor;
      ctx.beginPath();
      ctx.roundRect(boxX, boxY, boxW, boxH, 5);
      ctx.fill();

      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(text, boxX + boxW / 2, boxY + boxH / 2 + 0.5);
      ctx.restore();
    };

    if (activeSupportResistance) {
      drawHorizontalLevel(activeSupportResistance.resistance_1, "저항선", "#f04452", "rgba(240, 68, 82, 0.9)");
      drawHorizontalLevel(activeSupportResistance.support_1, "지지선", "#3182f6", "rgba(49, 130, 246, 0.9)");
    }

    // X축 날짜 레이블 (시작, 중간, 끝)
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const labelIndices = [0, Math.floor((series.length - 1) / 2), series.length - 1];
    labelIndices.forEach((idx) => {
      if (series[idx]) {
        ctx.fillStyle = "#64748b";
        ctx.fillText(series[idx].date.slice(5), getX(idx), height - pad.bottom + 8);
      }
    });

    // 라인 그리기 헬퍼
    const drawLine = (key, color, lineWidth) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.beginPath();
      let started = false;
      series.forEach((item, idx) => {
        const val = item[key];
        if (val == null) return;
        const x = getX(idx);
        const y = getY(val);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
    };

    drawLine("ma60", "#10b981", 1.8);
    drawLine("ma20", "#f59e0b", 1.8);
    drawLine("ma5", "#ef4444", 1.8);
    drawLine("close", (document.documentElement.getAttribute("data-theme") === "dark" ? "#f2f4f6" : "#191f28"), 2.2);

    // 마우스 호버 세로선 및 포인트 강조
    if (hoverIdx >= 0 && hoverIdx < series.length) {
      const hx = getX(hoverIdx);
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(hx, pad.top);
      ctx.lineTo(hx, height - pad.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      const item = series[hoverIdx];
      [["close", (document.documentElement.getAttribute("data-theme") === "dark" ? "#f2f4f6" : "#191f28")], ["ma5", "#ef4444"], ["ma20", "#f59e0b"], ["ma60", "#10b981"]].forEach(([k, c]) => {
        if (item[k] != null) {
          ctx.fillStyle = c;
          ctx.beginPath();
          ctx.arc(hx, getY(item[k]), 4, 0, Math.PI * 2);
          ctx.fill();
        }
      });
    }
  }

  async function runAnalyze(code) {
    const trimmed = code.trim();
    const isValidKr = /^\d{6}$/.test(trimmed);
    const isValidUs = /^[A-Za-z]{1,5}(\.[A-Za-z]{1,2})?$/.test(trimmed);
    if (!isValidKr && !isValidUs) {
      const msg = "국내 6자리 숫자 코드(예: 000660) 또는 미국 영문 티커(예: NVDA, AAPL)를 입력해 주세요.";
      console.error(`[ERROR]     오류 발생 (${msg})`);
      showErrors([msg]);
      return;
    }
    const normalized = isValidUs ? trimmed.toUpperCase() : trimmed;

    const mode = currentTab;
    const endpoint = mode === "fundamental" ? "/fetch" : "/technical";
    const aiAnswerEl = mode === "fundamental" ? fundAiAnswerEl : techAiAnswerEl;
    const chatFormEl = mode === "fundamental" ? fundChatForm : techChatForm;
    const quickQEl = mode === "fundamental" ? fundQuickQuestionsEl : techQuickQuestionsEl;
    const panelEl = mode === "fundamental" ? panelFundamental : panelTechnical;

    console.log(`[SEARCH]    데이터 수집 요청 시작 (${trimmed}, mode=${mode})`);
    showErrors([]);
    showStatus(`[${trimmed}] 데이터를 수집하고 있습니다...`);
    analyzeBtn.disabled = true;
    chatFormEl.classList.add("hidden");
    if (quickQEl) quickQEl.classList.add("hidden");

    try {
      // 1단계: 원천 데이터 수집
      const collectRes = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: trimmed }),
      });
      const collected = await collectRes.json();

      if (collected.errors && collected.errors.length > 0) {
        console.error(`[ERROR]     오류 발생 (${collected.errors.join(" / ")})`);
        showErrors(collected.errors);
      }

      const valid = mode === "fundamental" ? Boolean(collected.name) : Boolean(collected.price_summary && collected.price_summary.latest_close != null);
      if (!collectRes.ok && !valid) {
        panelEl.classList.add("hidden");
        return;
      }

      state[mode] = { code: trimmed, data: collected, conversationId: "" };

      if (mode === "fundamental") {
        renderFundamental(collected);
      } else {
        console.log(`[FDR]       기술적 지표 데이터 수신 완료 (${trimmed}, ${collected.price_summary.latest_close})`);
        renderTechnical(collected);
      }

      aiAnswerEl.innerHTML = "";
      const initialBubble = appendChatBubble(
        aiAnswerEl,
        "ai",
        "🤖 Dify AI 챗봇이 수집된 데이터를 분석하고 있습니다... (잠시만 기다려 주세요)"
      );
      panelEl.classList.remove("hidden");
      if (mode === "fundamental") {
        drawForeignDonut((collected.snapshot || {}).foreign_rate);
      } else {
        drawRsiDonut((collected.price_summary || {}).rsi_14);
        drawTechChart(activeChartSeries);
      }
      console.log("[RENDER]    화면 렌더링 완료");

      // 2단계: Dify AI 챗봇 분석 요청
      showStatus(`[${trimmed}] Dify AI 챗봇이 리포트를 작성 중입니다...`);
      const analyzeRes = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: trimmed,
          mode,
          cached_data: collected,
        }),
      });
      const analyzeData = await analyzeRes.json();

      if (analyzeData.errors && analyzeData.errors.length > 0) {
        console.error(`[ERROR]     오류 발생 (${analyzeData.errors.join(" / ")})`);
        showErrors(analyzeData.errors);
      }

      if (analyzeData.answer) {
        console.log(`[DIFY]      Dify 챗봇 분석 요청 및 응답 완료 (${mode})`);
        initialBubble.innerHTML = renderMarkdownSafe(analyzeData.answer);
        state[mode].conversationId = analyzeData.conversation_id || "";
        chatFormEl.classList.remove("hidden");
        if (quickQEl) quickQEl.classList.remove("hidden");
      } else {
        initialBubble.innerHTML = renderMarkdownSafe("⚠️ AI 분석 답변을 생성하지 못했습니다. 위 오류 메시지를 확인해 주세요.");
      }
    } catch (err) {
      console.error(`[ERROR]     오류 발생 (${err.message})`);
      showErrors(["서버와 통신하는 중 오류가 발생했습니다."]);
    } finally {
      hideStatus();
      analyzeBtn.disabled = false;
    }
  }

  async function sendFollowup(mode, inputEl, answerEl, formEl) {
    const question = inputEl.value.trim();
    if (!question) return;

    const convId = state[mode].conversationId;
    const code = state[mode].code;
    const submitBtn = formEl.querySelector("button");

    inputEl.value = "";
    submitBtn.disabled = true;
    appendChatBubble(answerEl, "user", question);
    const pendingBubble = appendChatBubble(answerEl, "ai", "🤖 답변 생성 중...");

    try {
      const res = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          mode,
          question,
          conversation_id: convId,
        }),
      });
      const data = await res.json();

      if (data.errors && data.errors.length > 0) {
        console.error(`[ERROR]     오류 발생 (${data.errors.join(" / ")})`);
        showErrors(data.errors);
      }

      if (data.answer) {
        console.log(`[DIFY]      Dify 챗봇 분석 요청 및 응답 완료 (${mode} 후속질문)`);
        pendingBubble.innerHTML = renderMarkdownSafe(data.answer);
        answerEl.scrollTop = answerEl.scrollHeight;
        if (data.conversation_id) {
          state[mode].conversationId = data.conversation_id;
        }
      } else {
        pendingBubble.innerHTML = renderMarkdownSafe("⚠️ 답변을 가져오지 못했습니다. (일시적 오류이거나 정책상 답변이 제한된 질문일 수 있습니다.)");
      }
    } catch (err) {
      console.error(`[ERROR]     오류 발생 (${err.message})`);
      showErrors(["후속 질문 전송 중 오류가 발생했습니다."]);
    } finally {
      submitBtn.disabled = false;
    }
  }

  // 이벤트 등록
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      switchTab(btn.dataset.tab);
    });
  });

  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    runAnalyze(codeInput.value);
  });

  exampleBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const code = btn.dataset.code || "";
      codeInput.value = code;
      runAnalyze(code);
    });
  });

  fundChatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendFollowup("fundamental", fundFollowupInput, fundAiAnswerEl, fundChatForm);
  });

  techChatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendFollowup("technical", techFollowupInput, techAiAnswerEl, techChatForm);
  });

  if (rebalChatForm) {
    rebalChatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      sendFollowup("rebalance", rebalFollowupInput, rebalAiAnswerEl, rebalChatForm);
    });
  }

  // 모든 탭의 추천 질문 칩 클릭 시 즉시 질문 전송
  document.querySelectorAll(".quick-q-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.mode;
      const q = btn.dataset.q || "";
      if (!q) return;
      if (mode === "fundamental") {
        fundFollowupInput.value = q;
        sendFollowup("fundamental", fundFollowupInput, fundAiAnswerEl, fundChatForm);
      } else if (mode === "technical") {
        techFollowupInput.value = q;
        sendFollowup("technical", techFollowupInput, techAiAnswerEl, techChatForm);
      } else if (mode === "rebalance") {
        rebalFollowupInput.value = q;
        sendFollowup("rebalance", rebalFollowupInput, rebalAiAnswerEl, rebalChatForm);
      }
    });
  });

  // ================= [탭 3] 리밸런싱 도우미 로직 =================
  const STORAGE_KEY = "investment_assistant_portfolio_v1";
  const DONUT_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#64748b"];
  const SAMPLE_PORTFOLIO = {
    cash: 2000000,
    cash_target_pct: 20,
    items: [
      { code: "000660", qty: 3, target_pct: 30 },
      { code: "005930", qty: 20, target_pct: 30 },
      { code: "035420", qty: 10, target_pct: 20 },
    ],
  };

  function updateTargetSumHint() {
    if (!rebalRowsEl || !rebalTargetSumHintEl) return;
    let sum = Number(rebalCashTargetInput ? rebalCashTargetInput.value : 0) || 0;
    rebalRowsEl.querySelectorAll(".rebal-target-input").forEach((inp) => {
      sum += Number(inp.value) || 0;
    });
    const rounded = Math.round(sum * 100) / 100;
    rebalTargetSumHintEl.textContent = `목표 비중 합계: ${rounded}%` + (Math.abs(rounded - 100) > 0.1 ? " (100%로 맞추는 것을 권장)" : " (완벽!)");
  }

  function savePortfolioToStorage() {
    if (!rebalRowsEl) return;
    const items = [];
    rebalRowsEl.querySelectorAll(".rebal-row").forEach((row) => {
      items.push({
        code: row.querySelector(".rebal-code-input").value.trim(),
        qty: Number(row.querySelector(".rebal-qty-input").value) || 0,
        target_pct: Number(row.querySelector(".rebal-target-input").value) || 0,
      });
    });
    const payload = {
      cash: Number(rebalCashInput ? rebalCashInput.value : 0) || 0,
      cash_target_pct: Number(rebalCashTargetInput ? rebalCashTargetInput.value : 0) || 0,
      items,
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (_) {}
    updateTargetSumHint();
  }

  function createRebalRow(item = { code: "", qty: 0, target_pct: 0 }) {
    if (!rebalRowsEl) return;
    const div = document.createElement("div");
    div.className = "rebal-row";
    div.innerHTML = `
      <div class="rebal-field">
        <label>종목코드 (6자리)</label>
        <input type="text" class="rebal-code-input" maxlength="6" placeholder="예: 000660" value="${escapeHtml(item.code || "")}" />
      </div>
      <div class="rebal-field">
        <label>보유 수량 (주)</label>
        <input type="number" class="rebal-qty-input" min="0" step="1" value="${escapeHtml(item.qty ?? 0)}" />
      </div>
      <div class="rebal-field">
        <label>목표 비중 (%)</label>
        <input type="number" class="rebal-target-input" min="0" max="100" step="1" value="${escapeHtml(item.target_pct ?? 0)}" />
      </div>
      <button type="button" class="rebal-del-btn">삭제</button>
    `;

    div.querySelectorAll("input").forEach((inp) => {
      inp.addEventListener("input", savePortfolioToStorage);
    });
    div.querySelector(".rebal-del-btn").addEventListener("click", () => {
      div.remove();
      savePortfolioToStorage();
    });
    rebalRowsEl.appendChild(div);
  }

  function loadPortfolio(portfolioData) {
    if (!rebalRowsEl) return;
    rebalRowsEl.innerHTML = "";
    const items = portfolioData.items && portfolioData.items.length > 0 ? portfolioData.items : SAMPLE_PORTFOLIO.items;
    items.forEach((it) => createRebalRow(it));
    if (rebalCashInput) rebalCashInput.value = portfolioData.cash ?? 0;
    if (rebalCashTargetInput) rebalCashTargetInput.value = portfolioData.cash_target_pct ?? 0;
    updateTargetSumHint();
  }

  function initPortfolio() {
    if (!rebalRowsEl) return;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        loadPortfolio(JSON.parse(saved));
        return;
      }
    } catch (_) {}
    loadPortfolio(SAMPLE_PORTFOLIO);
  }

  function drawMultiDonut(canvasEl, slices, centerTop, centerBottom) {
    if (!canvasEl) return;
    const size = 170;
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = size * dpr;
    canvasEl.height = size * dpr;

    const ctx = canvasEl.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    const cx = size / 2;
    const cy = size / 2;
    const radius = 64;
    const lineWidth = 24;
    const total = slices.reduce((acc, s) => acc + Math.max(0, s.value), 0);

    if (total <= 0) {
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    } else {
      let startAngle = -Math.PI / 2;
      slices.forEach((s) => {
        if (s.value <= 0) return;
        const sliceAngle = (s.value / total) * Math.PI * 2;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, startAngle + sliceAngle);
        ctx.strokeStyle = s.color;
        ctx.lineWidth = lineWidth;
        ctx.stroke();
        startAngle += sliceAngle;
      });
    }

    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = (document.documentElement.getAttribute("data-theme") === "dark" ? "#f2f4f6" : "#191f28");
    ctx.font = "bold 14px sans-serif";
    ctx.fillText(centerTop, cx, cy - 7);
    ctx.fillStyle = "#64748b";
    ctx.font = "11px sans-serif";
    ctx.fillText(centerBottom, cx, cy + 12);
  }

  function renderRebalanceDonuts(data) {
    const items = data.items || [];
    const cash = data.cash || { current_pct: 0, target_pct: 0 };

    const currentSlices = items.map((it, idx) => ({
      label: it.name,
      value: it.current_pct,
      color: DONUT_COLORS[idx % (DONUT_COLORS.length - 1)],
    }));
    currentSlices.push({ label: "현금", value: cash.current_pct, color: "#94a3b8" });

    const targetSlices = items.map((it, idx) => ({
      label: it.name,
      value: it.target_pct,
      color: DONUT_COLORS[idx % (DONUT_COLORS.length - 1)],
    }));
    targetSlices.push({ label: "현금", value: cash.target_pct, color: "#94a3b8" });

    drawMultiDonut(rebalCurrentDonutEl, currentSlices, formatKoreanWon(data.total_value), "현재 총자산");
    drawMultiDonut(rebalTargetDonutEl, targetSlices, `${data.target_sum_pct}%`, "목표 합계");

    if (rebalLegendEl) {
      rebalLegendEl.innerHTML = currentSlices
        .map(
          (s, idx) =>
            `<span class="legend-item"><i class="dot" style="background-color:${s.color}"></i>${escapeHtml(s.label)} (${s.value}% → ${targetSlices[idx].value}%)</span>`
        )
        .join("");
    }
  }

  function renderRebalanceResult(data) {
    if (rebalTotalBadgeEl) {
      rebalTotalBadgeEl.textContent = `총 자산: ${formatNumber(data.total_value)}원`;
    }

    if (rebalWarningsEl) {
      const warns = data.warnings || [];
      if (warns.length > 0) {
        rebalWarningsEl.innerHTML = warns.map((w) => `<p>⚠️ ${escapeHtml(w)}</p>`).join("");
        rebalWarningsEl.classList.remove("hidden");
      } else {
        rebalWarningsEl.classList.add("hidden");
      }
    }

    if (rebalTableBodyEl) {
      const rowsHtml = (data.items || [])
        .map((it) => {
          let actionHtml = `<span class="action-badge hold">유지</span>`;
          if (it.action === "BUY") {
            actionHtml = `<span class="action-badge buy">+${formatNumber(it.suggested_shares)}주 매수</span>`;
          } else if (it.action === "SELL") {
            actionHtml = `<span class="action-badge sell">${formatNumber(it.suggested_shares)}주 매도</span>`;
          }
          return `
            <tr>
              <td><strong>${escapeHtml(it.name)}</strong> (${escapeHtml(it.code)})</td>
              <td>${escapeHtml(formatNumber(it.current_price))}원</td>
              <td>${escapeHtml(formatNumber(it.qty))}주</td>
              <td>${escapeHtml(formatNumber(it.eval_amount))}원</td>
              <td>${it.current_pct}%</td>
              <td>${it.target_pct}%</td>
              <td>${actionHtml}</td>
            </tr>
          `;
        })
        .join("");

      const cash = data.cash || {};
      const cashDiffText =
        cash.diff_amount > 0
          ? `<span class="action-badge buy">+${formatNumber(cash.diff_amount)}원 확보</span>`
          : cash.diff_amount < 0
            ? `<span class="action-badge sell">${formatNumber(cash.diff_amount)}원 투입</span>`
            : `<span class="action-badge hold">유지</span>`;

      rebalTableBodyEl.innerHTML =
        rowsHtml +
        `
          <tr>
            <td><strong>현금 (예수금)</strong></td>
            <td>-</td>
            <td>-</td>
            <td>${escapeHtml(formatNumber(cash.amount))}원</td>
            <td>${cash.current_pct}%</td>
            <td>${cash.target_pct}%</td>
            <td>${cashDiffText}</td>
          </tr>
        `;
    }

    rebalanceResultEl.classList.remove("hidden");
    renderRebalanceDonuts(data);
  }

  async function runRebalanceCalc() {
    savePortfolioToStorage();
    const items = [];
    rebalRowsEl.querySelectorAll(".rebal-row").forEach((row) => {
      const code = row.querySelector(".rebal-code-input").value.trim();
      if (code) {
        items.push({
          code,
          qty: Number(row.querySelector(".rebal-qty-input").value) || 0,
          target_pct: Number(row.querySelector(".rebal-target-input").value) || 0,
        });
      }
    });

    if (items.length === 0) {
      showErrors(["최소 1개 이상의 종목코드를 입력해 주세요."]);
      return;
    }

    showErrors([]);
    showStatus("보유 종목의 실시간 시세를 조회하고 리밸런싱을 계산하고 있습니다...");
    rebalCalcBtn.disabled = true;

    try {
      const res = await fetch("/rebalance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items,
          cash: Number(rebalCashInput.value) || 0,
          cash_target_pct: Number(rebalCashTargetInput.value) || 0,
        }),
      });
      const data = await res.json();

      if (data.errors && data.errors.length > 0) {
        showErrors(data.errors);
      }
      if (!res.ok) return;

      state.rebalance = { code: "PORTFOLIO", data, conversationId: "" };
      renderRebalanceResult(data);
      rebalAiAnswerEl.innerHTML = "위 'AI 포트폴리오 진단 받기' 버튼을 누르면 현재 포트폴리오 비중과 리스크를 분석해 드립니다.";
      rebalChatForm.classList.add("hidden");
      if (rebalQuickQuestionsEl) rebalQuickQuestionsEl.classList.add("hidden");
      console.log("[RENDER]    리밸런싱 계산 및 도넛 차트 렌더링 완료");
    } catch (err) {
      console.error(`[ERROR]     오류 발생 (${err.message})`);
      showErrors(["리밸런싱 계산 중 서버 오류가 발생했습니다."]);
    } finally {
      hideStatus();
      rebalCalcBtn.disabled = false;
    }
  }

  async function runRebalanceAi() {
    if (!state.rebalance.data) {
      showErrors(["먼저 리밸런싱 계산을 실행해 주세요."]);
      return;
    }

    showErrors([]);
    showStatus("Dify AI가 내 포트폴리오를 진단하고 있습니다...");
    rebalAiBtn.disabled = true;
    rebalAiAnswerEl.innerHTML = "";
    const initialBubble = appendChatBubble(
      rebalAiAnswerEl,
      "ai",
      "🤖 Dify AI가 포트폴리오 비중과 리스크를 진단하고 있습니다... (잠시만 기다려 주세요)"
    );

    try {
      const res = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: "PORTFOLIO",
          mode: "rebalance",
          cached_data: state.rebalance.data,
        }),
      });
      const data = await res.json();

      if (data.errors && data.errors.length > 0) {
        showErrors(data.errors);
      }

      if (data.answer) {
        console.log("[DIFY]      Dify 챗봇 분석 요청 및 응답 완료 (rebalance)");
        initialBubble.innerHTML = renderMarkdownSafe(data.answer);
        state.rebalance.conversationId = data.conversation_id || "";
        rebalChatForm.classList.remove("hidden");
        if (rebalQuickQuestionsEl) rebalQuickQuestionsEl.classList.remove("hidden");
      } else {
        initialBubble.innerHTML = renderMarkdownSafe("⚠️ 포트폴리오 AI 진단을 생성하지 못했습니다. 위 오류 메시지를 확인해 주세요.");
      }
    } catch (err) {
      console.error(`[ERROR]     오류 발생 (${err.message})`);
      showErrors(["AI 포트폴리오 진단 중 오류가 발생했습니다."]);
    } finally {
      hideStatus();
      rebalAiBtn.disabled = false;
    }
  }

  if (rebalAddRowBtn) {
    rebalAddRowBtn.addEventListener("click", () => {
      createRebalRow({ code: "", qty: 0, target_pct: 0 });
      savePortfolioToStorage();
    });
  }
  if (rebalSampleBtn) {
    rebalSampleBtn.addEventListener("click", () => {
      loadPortfolio(SAMPLE_PORTFOLIO);
      savePortfolioToStorage();
    });
  }
  document.querySelectorAll(".rebal-preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cashPct = Number(btn.dataset.cashPct) || 20;
      const rows = rebalRowsEl ? rebalRowsEl.querySelectorAll(".rebal-row") : [];
      if (rebalCashTargetInput) rebalCashTargetInput.value = cashPct;
      if (rows.length > 0) {
        const remain = 100 - cashPct;
        const base = Math.floor(remain / rows.length);
        let extra = remain - base * rows.length;
        rows.forEach((row) => {
          const val = base + (extra > 0 ? 1 : 0);
          if (extra > 0) extra -= 1;
          row.querySelector(".rebal-target-input").value = val;
        });
      }
      savePortfolioToStorage();
    });
  });
  if (rebalCashInput) rebalCashInput.addEventListener("input", savePortfolioToStorage);
  if (rebalCashTargetInput) rebalCashTargetInput.addEventListener("input", savePortfolioToStorage);
  if (rebalCalcBtn) rebalCalcBtn.addEventListener("click", runRebalanceCalc);
  if (rebalAiBtn) rebalAiBtn.addEventListener("click", runRebalanceAi);

  initPortfolio();

  if (techChartEl) {
    techChartEl.addEventListener("mousemove", (e) => {
      if (!activeChartSeries || activeChartSeries.length === 0) return;
      const rect = techChartEl.getBoundingClientRect();
      const padLeft = 74;
      const padRight = 16;
      const plotW = rect.width - padLeft - padRight;
      const relX = e.clientX - rect.left - padLeft;
      if (relX < 0 || relX > plotW) {
        chartTooltipEl.classList.add("hidden");
        drawTechChart(activeChartSeries, -1);
        return;
      }

      const idx = Math.min(
        activeChartSeries.length - 1,
        Math.max(0, Math.round((relX / plotW) * (activeChartSeries.length - 1)))
      );
      const item = activeChartSeries[idx];
      drawTechChart(activeChartSeries, idx);

      chartTooltipEl.innerHTML = `
        <strong>${escapeHtml(item.date)}</strong><br/>
        종가: ${escapeHtml(formatPrice(item.close, activeChartCurrency))}<br/>
        MA5: ${escapeHtml(formatPrice(item.ma5, activeChartCurrency))}<br/>
        MA20: ${escapeHtml(formatPrice(item.ma20, activeChartCurrency))}<br/>
        MA60: ${escapeHtml(formatPrice(item.ma60, activeChartCurrency))}
      `;
      chartTooltipEl.classList.remove("hidden");

      const tipLeft = e.clientX - rect.left + 12;
      const maxLeft = rect.width - chartTooltipEl.offsetWidth - 8;
      chartTooltipEl.style.left = `${Math.max(8, Math.min(tipLeft, maxLeft))}px`;
      chartTooltipEl.style.top = "12px";
    });

    techChartEl.addEventListener("mouseleave", () => {
      chartTooltipEl.classList.add("hidden");
      drawTechChart(activeChartSeries, -1);
    });
  }

  window.addEventListener("resize", () => {
    if (currentTab === "technical" && activeChartSeries.length > 0) {
      drawTechChart(activeChartSeries);
    }
  });
});
