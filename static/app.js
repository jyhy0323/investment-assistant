document.addEventListener("DOMContentLoaded", () => {
  console.log("[PAGE]      페이지 로드 완료 (모드: main)");

  let currentTab = "fundamental"; // 'fundamental' | 'technical'
  const state = {
    fundamental: { code: "", data: null, conversationId: "" },
    technical: { code: "", data: null, conversationId: "" },
  };

  // 공통 요소
  const tabBtns = document.querySelectorAll(".tab-btn");
  const searchForm = document.getElementById("search-form");
  const codeInput = document.getElementById("stock-code");
  const analyzeBtn = document.getElementById("analyze-btn");
  const exampleBtns = document.querySelectorAll(".example-btn");
  const statusMessage = document.getElementById("status-message");
  const errorBox = document.getElementById("error-box");

  // 패널 요소
  const panelFundamental = document.getElementById("panel-fundamental");
  const panelTechnical = document.getElementById("panel-technical");

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
  const newsListEl = document.getElementById("news-list");

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
  let activeChartSeries = [];

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

  function switchTab(nextTab) {
    currentTab = nextTab;
    console.log(`[TAB]       탭 전환 (${currentTab})`);

    tabBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === currentTab);
    });

    showErrors([]);
    if (currentTab === "fundamental") {
      panelTechnical.classList.add("hidden");
      if (state.fundamental.data) {
        panelFundamental.classList.remove("hidden");
      }
    } else {
      panelFundamental.classList.add("hidden");
      if (state.technical.data) {
        panelTechnical.classList.remove("hidden");
        drawTechChart(activeChartSeries);
      }
    }
  }

  function renderFundamental(data) {
    const snap = data.snapshot || {};
    stockNameEl.textContent = data.name || "알 수 없음";
    stockCodeBadgeEl.textContent = data.code || "-";
    currentPriceEl.textContent =
      snap.current_price != null ? `${formatNumber(snap.current_price)}원` : "-";

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

    marketCapEl.textContent = formatKoreanWon(snap.market_cap);
    perValueEl.textContent = snap.per != null ? `${snap.per}배` : "-";
    pbrValueEl.textContent = snap.pbr != null ? `${snap.pbr}배` : "-";

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
  }

  function renderTechnical(data) {
    const summary = data.price_summary || {};
    techAsOfEl.textContent = `기준일: ${data.as_of || "-"}`;
    techCloseEl.textContent = summary.latest_close != null ? `${formatNumber(summary.latest_close)}원` : "-";
    techVolumeEl.textContent = summary.volume != null ? `${formatNumber(summary.volume)}주` : "-";
    techRsiEl.textContent = summary.rsi_14 != null ? `${summary.rsi_14}` : "-";
    techMa5El.textContent = summary.ma5 != null ? `${formatNumber(summary.ma5)}원` : "-";
    techMa20El.textContent = summary.ma20 != null ? `${formatNumber(summary.ma20)}원` : "-";
    techMa60El.textContent = summary.ma60 != null ? `${formatNumber(summary.ma60)}원` : "-";
    techHigh20El.textContent = summary.high_20d != null ? `${formatNumber(summary.high_20d)}원` : "-";
    techLow20El.textContent = summary.low_20d != null ? `${formatNumber(summary.low_20d)}원` : "-";

    candlesBodyEl.innerHTML = "";
    const candles = [...(data.recent_candles || [])].reverse();
    if (candles.length === 0) {
      candlesBodyEl.innerHTML = `<tr><td colspan="6" style="text-align:center;">일봉 데이터가 없습니다.</td></tr>`;
    } else {
      candles.forEach((c) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${escapeHtml(c.date)}</td>
          <td>${escapeHtml(formatNumber(c.open))}</td>
          <td>${escapeHtml(formatNumber(c.high))}</td>
          <td>${escapeHtml(formatNumber(c.low))}</td>
          <td><strong>${escapeHtml(formatNumber(c.close))}</strong></td>
          <td>${escapeHtml(formatNumber(c.volume))}</td>
        `;
        candlesBodyEl.appendChild(tr);
      });
    }

    activeChartSeries = data.chart_series || [];
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

    const pad = { top: 18, right: 16, bottom: 28, left: 74 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    // 최소/최대 가격 범위 계산
    const values = [];
    series.forEach((item) => {
      ["close", "ma5", "ma20", "ma60"].forEach((k) => {
        if (item[k] != null) values.push(item[k]);
      });
    });
    if (values.length === 0) return;

    let minVal = Math.min(...values);
    let maxVal = Math.max(...values);
    const span = maxVal - minVal || 1;
    minVal = minVal - span * 0.06;
    maxVal = maxVal + span * 0.06;

    const getX = (idx) => pad.left + (series.length === 1 ? plotW / 2 : (idx / (series.length - 1)) * plotW);
    const getY = (val) => pad.top + ((maxVal - val) / (maxVal - minVal)) * plotH;

    // 가로 눈금선 및 Y축 가격 레이블 (5줄)
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const ratio = i / 4;
      const y = pad.top + ratio * plotH;
      const priceVal = Math.round(maxVal - ratio * (maxVal - minVal));

      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();

      ctx.fillStyle = "#64748b";
      ctx.fillText(formatNumber(priceVal), pad.left - 8, y);
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
    drawLine("close", "#0f172a", 2.2);

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
      [["close", "#0f172a"], ["ma5", "#ef4444"], ["ma20", "#f59e0b"], ["ma60", "#10b981"]].forEach(([k, c]) => {
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
    if (!/^\d{6}$/.test(trimmed)) {
      const msg = "종목코드는 6자리 숫자여야 합니다. (예: 000660)";
      console.error(`[ERROR]     오류 발생 (${msg})`);
      showErrors([msg]);
      return;
    }

    const mode = currentTab;
    const endpoint = mode === "fundamental" ? "/fetch" : "/technical";
    const aiAnswerEl = mode === "fundamental" ? fundAiAnswerEl : techAiAnswerEl;
    const chatFormEl = mode === "fundamental" ? fundChatForm : techChatForm;
    const panelEl = mode === "fundamental" ? panelFundamental : panelTechnical;

    console.log(`[SEARCH]    데이터 수집 요청 시작 (${trimmed}, mode=${mode})`);
    showErrors([]);
    showStatus(`[${trimmed}] 데이터를 수집하고 있습니다...`);
    analyzeBtn.disabled = true;
    chatFormEl.classList.add("hidden");

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

      aiAnswerEl.textContent = "🤖 Dify AI 챗봇이 수집된 데이터를 분석하고 있습니다... (잠시만 기다려 주세요)";
      panelEl.classList.remove("hidden");
      if (mode === "technical") {
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
        aiAnswerEl.textContent = analyzeData.answer;
        state[mode].conversationId = analyzeData.conversation_id || "";
        chatFormEl.classList.remove("hidden");
      } else {
        aiAnswerEl.textContent = "⚠️ AI 분석 답변을 생성하지 못했습니다. 위 오류 메시지를 확인해 주세요.";
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
    answerEl.textContent += `\n\n🙋 질문: ${question}\n🤖 답변 생성 중...`;

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
        answerEl.textContent = answerEl.textContent.replace("🤖 답변 생성 중...", `🤖 ${data.answer}`);
        if (data.conversation_id) {
          state[mode].conversationId = data.conversation_id;
        }
      } else {
        answerEl.textContent = answerEl.textContent.replace("🤖 답변 생성 중...", "⚠️ 답변을 가져오지 못했습니다.");
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
        종가: ${escapeHtml(formatNumber(item.close))}원<br/>
        MA5: ${item.ma5 != null ? escapeHtml(formatNumber(item.ma5)) + "원" : "-"}<br/>
        MA20: ${item.ma20 != null ? escapeHtml(formatNumber(item.ma20)) + "원" : "-"}<br/>
        MA60: ${item.ma60 != null ? escapeHtml(formatNumber(item.ma60)) + "원" : "-"}
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
