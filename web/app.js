/* ═══ SIGINT Dashboard — app.js (v2 icons + fixed layout + caching) ═══ */
let API = 'http://localhost:8080';
const PORTAS = ['5050', '5051', '5052'];
let dadosGlobais = [], pausado = false, _visible = true;

// Caches para evitar reflow do DOM e renderizações desnecessárias
let dadosCache = "";
let statsCache = "";
let healthCache = "";

document.addEventListener('visibilitychange', () => {
    _visible = !document.hidden;
    if (_visible) { fetchDados(); fetchHealth(); fetchStats(); }
});

async function checkHealth() {
    let activeApi = null;
    for (let porta of PORTAS) {
        const url = `http://localhost:${porta}`;
        try {
            const r = await fetch(url + '/api/health', { signal: AbortSignal.timeout(1500) });
            if (r.ok) {
                document.getElementById(`dot-${porta}`).className = 'dot dot-green';
                if (!activeApi) activeApi = url;
            } else {
                document.getElementById(`dot-${porta}`).className = 'dot dot-red';
            }
        } catch(e) {
            document.getElementById(`dot-${porta}`).className = 'dot dot-red';
        }
    }
    // O Load Balancer (8080) é o principal. As pings acima servem só para a UI.
}

function mudarAba(aba) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('panel-' + aba).classList.add('active');
    document.getElementById('tab-' + aba).classList.add('active');
    if (aba === 'scores') fetchScores();
    if (aba === 'mensagens') fetchMensagens();
}

async function fetchHealth() {
    if (!_visible || !API) return;
    const badge = document.getElementById('health-badge');
    try {
        const r = await fetch(API + '/api/health');
        const j = await r.json();
        const cacheStr = JSON.stringify(j);
        if (cacheStr === healthCache) return; // Retorna cedo se nada mudou
        healthCache = cacheStr;

        const up = j.uptime_seconds;
        const m = Math.floor(up / 60), s = Math.floor(up % 60);
        const rabbit = j.rabbitmq === 'online';
        badge.innerHTML = `<span class="dot ${rabbit ? 'dot-green' : 'dot-red'}"></span> Buffer Online · RabbitMQ ${rabbit ? 'OK' : 'OFF'} · ${m}m${s}s`;
    } catch (e) {
        badge.innerHTML = '<span class="dot dot-red"></span> Buffer Offline';
        healthCache = "";
    }
}

async function fetchStats() {
    if (!_visible || !API) return;
    try {
        const r = await fetch(API + '/api/stats');
        const j = await r.json();
        const cacheStr = JSON.stringify(j);
        if (cacheStr === statsCache) return; // Retorna cedo se nada mudou
        statsCache = cacheStr;

        document.getElementById('s-msgs').textContent = j.total_mensagens ?? 0;
        document.getElementById('s-pkts').textContent = j.total_pacotes ?? 0;
        document.getElementById('s-proc').textContent = j.pacotes_processados ?? 0;
        document.getElementById('s-pend').textContent = j.pacotes_pendentes ?? 0;
        document.getElementById('s-integ').textContent = (j.media_integridade ?? 0) + '%';
        document.getElementById('s-lat').textContent = (j.media_latencia_ms ?? 0) + 'ms';
    } catch (e) {}
}

function togglePause() {
    pausado = !pausado;
    const b = document.getElementById('btn-pause');
    b.innerHTML = pausado
        ? '<i data-lucide="play" class="icon-sm"></i> Retomar'
        : '<i data-lucide="pause" class="icon-sm"></i> Pausar';
    if (pausado) b.classList.add('btn-accent'); else b.classList.remove('btn-accent');
    lucide.createIcons();
}

async function fetchDados() {
    if (pausado || !_visible || !API) return;
    try {
        const r = await fetch(API + '/api/status');
        const j = await r.json();
        const cacheStr = JSON.stringify(j.pacotes);
        if (cacheStr === dadosCache) return; // Retorna cedo se não há novos pacotes
        dadosCache = cacheStr;

        dadosGlobais = j.pacotes || [];
        renderizar();
    } catch (e) {
        document.getElementById('logs').innerHTML = '<div class="vazio" style="color:var(--neon-red)">Buffer offline!</div>';
        document.getElementById('resultados').innerHTML = '<div class="vazio" style="color:var(--neon-red)">Buffer offline!</div>';
        dadosGlobais = [];
        dadosCache = "";
    }
}

function renderizar() {
    const busca = document.getElementById('busca').value.toLowerCase();
    const logBox = document.getElementById('logs');
    const resBox = document.getElementById('resultados');
    const investigando = logBox.scrollTop > 5 || logBox.matches(':hover');

    if (investigando) {
        logBox.classList.add('frozen');
    } else {
        logBox.classList.remove('frozen');
        logBox.innerHTML = dadosGlobais.map(p => `
            <div class="log-entry">
                <span class="status-tag">[${p.status.toUpperCase()}]</span> Pct ${p.ordem + 1}/${p.total}<br>
                <div class="signal-box">RAW: ${p.morse || '...'}</div>
                <span class="log-result">&gt; ${p.texto || 'Processando...'}</span>
            </div>
        `).join('') || '<div class="vazio">Sem dados...</div>';
    }

    const grupos = {};
    dadosGlobais.forEach(p => {
        if (!grupos[p.message_id]) grupos[p.message_id] = [];
        grupos[p.message_id].push(p);
    });

    let html = '';
    Object.keys(grupos).forEach(id => {
        const pcts = grupos[id].sort((a, b) => a.ordem - b.ordem);
        if (pcts.length === pcts[0].total && pcts.every(p => p.status !== 'recebido')) {
            const texto = pcts.map(p => p.texto).join('');
            if (texto.toLowerCase().includes(busca)) {
                html += `<div class="msg-final">
                    <button class="btn btn-copy" onclick="navigator.clipboard.writeText('${texto.replace(/'/g, "\\'")}')"><i data-lucide="copy" class="icon-xs"></i> Copiar</button>
                    <small>ID: ${id}</small>
                    <strong>${texto}</strong>
                </div>`;
            }
        }
    });
    resBox.innerHTML = html || '<div class="vazio">Nenhuma mensagem completa.</div>';
    lucide.createIcons();
}

function exportarTxt() {
    const t = document.getElementById('resultados').innerText;
    const b = new Blob([t], { type: 'text/plain' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(b);
    a.download = 'sigint_logs.txt'; a.click();
}

async function fetchScores() {
    const grid = document.getElementById('scores-grid');
    try {
        const r = await fetch(API + '/api/scores');
        const j = await r.json();
        const scores = j.scores || [];
        if (!scores.length) { grid.innerHTML = '<div class="vazio">Nenhum score disponível.</div>'; return; }
        grid.innerHTML = scores.map(s => {
            const integ = s.score_integridade ?? 0, reconst = s.score_reconstrucao ?? 0;
            const lat = s.latencia_media_ms ?? 0, ok = s.pacotes_ok ?? 0, total = s.total_pacotes ?? 0;
            const cI = integ >= 90 ? 'var(--neon-green)' : integ >= 60 ? 'var(--neon-yellow)' : 'var(--neon-red)';
            const cR = reconst >= 90 ? 'var(--neon-green)' : reconst >= 60 ? 'var(--neon-yellow)' : 'var(--neon-red)';
            return `<div class="score-card">
                <div class="msg-id"><i data-lucide="mail" class="icon-xs"></i> ${s.message_id}</div>
                <div class="score-metrics">
                    <div class="metric"><div class="metric-value" style="color:${cI}">${integ}%</div><div class="metric-label">Integridade</div></div>
                    <div class="metric"><div class="metric-value" style="color:${cR}">${reconst}%</div><div class="metric-label">Reconstrução</div></div>
                    <div class="metric"><div class="metric-value" style="color:var(--neon-cyan)">${lat}ms</div><div class="metric-label">Latência</div></div>
                    <div class="metric"><div class="metric-value">${ok}/${total}</div><div class="metric-label">Pacotes OK</div></div>
                </div>
                <div class="bar-container">
                    <div class="bar-label"><span>Integridade</span><span style="color:${cI}">${integ}%</span></div>
                    <div class="bar-track"><div class="bar-fill" style="width:${integ}%;background:${cI}"></div></div>
                </div>
                <div class="bar-container">
                    <div class="bar-label"><span>Reconstrução</span><span style="color:${cR}">${reconst}%</span></div>
                    <div class="bar-track"><div class="bar-fill" style="width:${reconst}%;background:${cR}"></div></div>
                </div>
                <div class="score-ts"><i data-lucide="clock" class="icon-xs"></i> ${s.ts_score || '—'}</div>
            </div>`;
        }).join('');
        lucide.createIcons();
    } catch (e) { grid.innerHTML = '<div class="vazio" style="color:var(--neon-red)">Erro ao buscar scores.</div>'; }
}

async function fetchMensagens() {
    const el = document.getElementById('mensagens-list');
    try {
        const r = await fetch(API + '/api/mensagens');
        const j = await r.json();
        const msgs = j.mensagens || [];
        if (!msgs.length) { el.innerHTML = '<div class="vazio">Nenhuma mensagem decodificada.</div>'; return; }
        el.innerHTML = msgs.map(m => `
            <div class="msg-list-item">
                <div class="msg-head">
                    <span style="font-size:.73rem;color:var(--muted);font-family:monospace;"><i data-lucide="mail" class="icon-xs"></i> ${m.message_id}</span>
                    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        <span style="font-size:.7rem;color:var(--muted);">${m.total_pacotes} pacotes · ${m.ts_recebido || ''}</span>
                        <button class="btn" style="font-size:.68rem;padding:5px 12px;" onclick="irParaValidar('${m.message_id}')" title="Validar"><i data-lucide="search" class="icon-xs"></i> Validar</button>
                        <button class="btn" style="font-size:.68rem;padding:5px 12px;" onclick="navigator.clipboard.writeText('${m.message_id}')" title="Copiar ID"><i data-lucide="copy" class="icon-xs"></i> ID</button>
                        <button class="btn btn-danger" style="font-size:.68rem;padding:5px 12px;" onclick="deletarMensagem(event,'${m.message_id}')" title="Excluir"><i data-lucide="trash-2" class="icon-xs"></i></button>
                    </div>
                </div>
                <div class="msg-text">${m.texto}</div>
            </div>
        `).join('');
        lucide.createIcons();
    } catch (e) { el.innerHTML = '<div class="vazio" style="color:var(--neon-red)">Buffer offline.</div>'; }
}

function irParaValidar(msgId) {
    document.getElementById('input-msg-id').value = msgId;
    mudarAba('validar');
    rodarValidacao();
}

async function exportarJson() {
    try {
        const r = await fetch(API + '/api/exportar');
        const j = await r.json();
        const b = new Blob([JSON.stringify(j, null, 2)], { type: 'application/json' });
        const a = document.createElement('a'); a.href = URL.createObjectURL(b);
        a.download = 'sigint_export.json'; a.click();
    } catch (e) { alert('Erro: Buffer offline!'); }
}

async function limparBanco() {
    if (!confirm('Isso apagará TODOS os dados. Continuar?')) return;
    try {
        await fetch(API + '/api/limpar', { method: 'POST' });
        fetchMensagens(); fetchStats(); fetchDados();
    } catch(e) { alert('Erro: ' + e); }
}

async function deletarMensagem(event, id) {
    event.stopPropagation();
    if (!confirm('Excluir esta mensagem permanentemente?')) return;
    try {
        const r = await fetch(API + '/api/mensagem/deletar/' + id, { method: 'DELETE' });
        if (r.ok) { fetchMensagens(); fetchStats(); fetchDados(); }
    } catch (e) { alert('Erro ao deletar: ' + e); }
}

async function rodarValidacao() {
    const msgId = document.getElementById('input-msg-id').value.trim();
    if (!msgId) { document.getElementById('input-msg-id').focus(); return; }

    const btn = document.getElementById('btn-validar');
    const iconEl = document.getElementById('btn-validar-icon');
    const resultado = document.getElementById('val-resultado');
    const vazio = document.getElementById('val-vazio');

    btn.disabled = true;
    iconEl.setAttribute('data-lucide', 'loader');
    lucide.createIcons();
    resultado.classList.remove('visivel');
    vazio.textContent = 'Consultando dicionário...';
    vazio.style.display = 'block';

    try {
        const r = await fetch(`${API}/api/validar/${msgId}`);
        if (!r.ok) {
            const err = await r.json();
            vazio.textContent = `Erro: ${err.msg || 'Mensagem não encontrada.'}`;
            return;
        }
        const j = await r.json();

        document.getElementById('val-original').textContent = j.texto_original;
        document.getElementById('val-reconstruido').textContent = j.texto_reconstruido;
        document.getElementById('val-chips').innerHTML = (j.palavras || []).map(p =>
            `<span class="chip ${p.valida ? 'chip-ok' : 'chip-fail'}"><i data-lucide="${p.valida ? 'check' : 'x'}" class="icon-xs"></i> ${p.palavra}</span>`
        ).join('');

        const cor = j.score_validacao >= 80 ? 'var(--neon-green)' : j.score_validacao >= 50 ? 'var(--neon-yellow)' : 'var(--neon-red)';
        document.getElementById('val-score').innerHTML = `<span style="color:${cor}">${j.score_validacao}%</span>`;
        document.getElementById('val-total').textContent = j.total_palavras;
        document.getElementById('val-tempo').textContent = j.tempo_ms + 'ms';
        document.getElementById('val-api-info').textContent = j.api_usada || '';

        vazio.style.display = 'none';
        resultado.classList.add('visivel');
        lucide.createIcons();
    } catch (e) {
        vazio.textContent = 'Erro de conexão. O buffer.py está rodando?';
    } finally {
        btn.disabled = false;
        iconEl.setAttribute('data-lucide', 'search');
        lucide.createIcons();
    }
}

setInterval(() => { if(_visible){checkHealth();} }, 5000);
setInterval(() => { if(_visible){fetchDados(); fetchHealth(); fetchStats();} }, 2500);
checkHealth(); fetchDados(); fetchHealth(); fetchStats();

const MORSE_DICT = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..',
    'E': '.', 'F': '..-.', 'G': '--.', 'H': '....',
    'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.',
    'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..', 'Ç': '-.-.', 'ç': '-.-.'
};

function limparTexto(texto) {
    let limpo = texto.toUpperCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
    return limpo.replace(/[^A-Z ]/g, '');
}

function encodeMorseBinario(texto) {
    const limpo = limparTexto(texto);
    const palavras = limpo.split(/\s+/);
    let morse = palavras.map(palavra => {
        let letras = [];
        for (let letra of palavra) {
            if (MORSE_DICT[letra]) letras.push(MORSE_DICT[letra]);
        }
        return letras.join(' ');
    }).join(' / ');

    let binario = "";
    const pM = morse.split(" / ");
    for (let p of pM) {
        const letras = p.split(" ");
        for (let l of letras) {
            for (let s of l) {
                if (s === '.') binario += "1";
                else if (s === '-') binario += "111";
                binario += "0";
            }
            binario += "000";
        }
        binario += "0000000";
    }
    return binario;
}

function encodeCesar(texto, shift = 3) {
    const limpo = limparTexto(texto);
    let resultado = "";
    for (let i = 0; i < limpo.length; i++) {
        let charCode = limpo.charCodeAt(i);
        if (charCode === 32) {
            resultado += " ";
        } else if (charCode >= 65 && charCode <= 90) {
            let novoCodigo = charCode - 65 + shift;
            resultado += String.fromCharCode((novoCodigo % 26) + 65);
        }
    }
    return resultado;
}

async function enviarMensagemSimulador() {
    const input = document.getElementById('sim-msg');
    const select = document.getElementById('sim-cifra');
    const btn = document.getElementById('btn-sim-enviar');
    const msgBruta = input.value.trim();
    
    if (!msgBruta) {
        alert("Por favor, digite uma mensagem.");
        input.focus();
        return;
    }

    const cifra = select.value;
    let payload = "";
    if (cifra === '&') {
        payload = encodeMorseBinario(msgBruta);
    } else if (cifra === '$') {
        payload = encodeCesar(msgBruta);
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" class="icon-sm"></i> Enviando...';
    lucide.createIcons();
    
    try {
        const r = await fetch(API + '/receber', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mensagem: payload,
                cifra: cifra
            })
        });
        
        if (r.ok) {
            input.value = '';
            fetchDados(); // Atualiza a tela na hora
        } else {
            alert("Erro ao enviar mensagem.");
        }
    } catch (e) {
        alert("Erro de conexão! O Buffer está online?");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="zap" class="icon-sm"></i> Enviar';
        lucide.createIcons();
    }
}
