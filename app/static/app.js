/* Lector de Facturas — comportamiento de la página (sin dependencias). */
(function () {
  "use strict";

  const LIMITES = window.LIMITES || { extensiones: [".jpg", ".jpeg", ".png", ".pdf"], tamano_maximo_mb: 10 };
  const $ = (id) => document.getElementById(id);
  const estado = { respuesta: null, pagina: 0, reloj: null };

  const CONFIANZA = { alta: "Alta", media: "Media", baja: "Baja", sin_valor: "No detectado" };
  const CORTO = { tax_id: "RUC", date: "Fecha", document_number: "Número", subtotal: "Subtotal", tax: "IVA", total: "Total" };

  // ---------- navegación ----------
  document.querySelectorAll(".pestana").forEach((boton) => {
    boton.addEventListener("click", () => mostrarVista(boton.dataset.vista));
  });

  function mostrarVista(nombre) {
    document.querySelectorAll(".pestana").forEach((b) => {
      if (b.dataset.vista === nombre) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    });
    $("vista-leer").hidden = nombre !== "leer";
    $("vista-acerca").hidden = nombre !== "acerca";
    if (nombre === "acerca") cargarAcerca();
  }

  // ---------- estados de la vista Leer ----------
  function mostrar(seccion) {
    ["inicio", "procesando", "resultado"].forEach((id) => { $(id).hidden = id !== seccion; });
    if (seccion !== "inicio") $("mensaje").hidden = true;
  }

  function mostrarError(texto) {
    detenerReloj();
    mostrar("inicio");
    $("mensaje-texto").textContent = texto;
    $("mensaje").hidden = false;
    $("archivo").value = "";
    $("mensaje").scrollIntoView({ block: "nearest" });
  }

  $("mensaje-cerrar").addEventListener("click", () => {
    $("mensaje").hidden = true;
    $("archivo").focus();
  });
  $("leer-otro").addEventListener("click", () => {
    estado.respuesta = null;
    $("archivo").value = "";
    mostrar("inicio");
    $("archivo").focus();
  });

  // ---------- carga del archivo ----------
  const zona = $("zona");
  $("archivo").addEventListener("change", (e) => { if (e.target.files[0]) enviarArchivo(e.target.files[0]); });
  ["dragenter", "dragover"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add("activa"); }));
  ["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.remove("activa"); }));
  zona.addEventListener("drop", (e) => {
    const archivo = e.dataTransfer && e.dataTransfer.files[0];
    if (archivo) enviarArchivo(archivo);
  });

  // Validación en el navegador: evita subir algo que el servidor va a rechazar.
  function validarEnNavegador(archivo) {
    const punto = archivo.name.lastIndexOf(".");
    const extension = punto >= 0 ? archivo.name.slice(punto).toLowerCase() : "";
    if (!LIMITES.extensiones.includes(extension)) {
      return `«${archivo.name}» no es una imagen ni un PDF. Sube un archivo JPG, PNG o PDF.`;
    }
    if (archivo.size === 0) return `«${archivo.name}» está vacío.`;
    if (archivo.size > LIMITES.tamano_maximo_mb * 1024 * 1024) {
      const mb = (archivo.size / 1024 / 1024).toFixed(1).replace(".", ",");
      return `«${archivo.name}» pesa ${mb} MB y el máximo es ${LIMITES.tamano_maximo_mb} MB. Reduce la resolución o comprime el PDF.`;
    }
    return null;
  }

  function enviarArchivo(archivo) {
    const problema = validarEnNavegador(archivo);
    if (problema) { mostrarError(problema); return; }
    const datos = new FormData();
    datos.append("archivo", archivo);
    procesar("/api/leer", datos, archivo.name);
  }

  document.querySelectorAll("[data-ejemplo]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const titulo = boton.querySelector("strong").textContent;
      procesar(`/api/ejemplo/${encodeURIComponent(boton.dataset.ejemplo)}`, null, `Ejemplo: ${titulo}`);
    });
  });

  async function procesar(url, cuerpo, nombre) {
    mostrar("procesando");
    $("procesando-archivo").textContent = nombre;
    iniciarReloj();
    let respuesta;
    try {
      respuesta = await fetch(url, { method: "POST", body: cuerpo });
    } catch (_e) {
      mostrarError("No hay conexión con el servidor. Revisa tu Internet y vuelve a intentar.");
      return;
    }
    let datos = null;
    try { datos = await respuesta.json(); } catch (_e) { /* respuesta no JSON */ }
    detenerReloj();
    if (!respuesta.ok || !datos || datos.error) {
      const texto = (datos && datos.error) ||
        (respuesta.status === 413 ? `El archivo supera el máximo de ${LIMITES.tamano_maximo_mb} MB.` :
          "El servidor no pudo procesar el documento. Vuelve a intentar en unos segundos.");
      mostrarError(texto);
      return;
    }
    estado.respuesta = datos;
    estado.pagina = 0;
    pintarResultado();
  }

  function iniciarReloj() {
    const inicio = Date.now();
    const pasos = [[0, "Revisando el archivo…"], [1500, "Leyendo el documento con 10 lecturas de Tesseract…"],
      [9000, "Comparando las lecturas y eligiendo cada valor…"], [25000, "Sigue leyendo: los documentos grandes o con varias páginas tardan más…"]];
    $("procesando-tiempo").textContent = "0";
    estado.reloj = setInterval(() => {
      const ms = Date.now() - inicio;
      $("procesando-tiempo").textContent = Math.floor(ms / 1000);
      const paso = pasos.filter((p) => p[0] <= ms).pop();
      $("procesando-paso").textContent = paso[1];
    }, 500);
  }
  function detenerReloj() { if (estado.reloj) clearInterval(estado.reloj); estado.reloj = null; }

  // ---------- resultado ----------
  function pintarResultado() {
    const r = estado.respuesta;
    mostrar("resultado");
    $("resultado-titulo").textContent = r.archivo;
    const paginas = r.paginas.length;
    const textoEstado = r.estado === "ok" ? "Lectura completa" : r.estado === "parcial" ? "Lectura parcial: alguna página falló" : "No se pudo leer";
    $("resultado-resumen").textContent = `${textoEstado}. ${paginas === 1 ? "1 página" : paginas + " páginas"} en ${String(r.segundos).replace(".", ",")} s.`;
    const selector = $("paginas-selector");
    selector.innerHTML = "";
    selector.hidden = paginas < 2;
    r.paginas.forEach((p, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = `Página ${p.numero}`;
      b.setAttribute("aria-pressed", String(i === estado.pagina));
      b.addEventListener("click", () => { estado.pagina = i; pintarResultado(); });
      selector.appendChild(b);
    });
    pintarPagina(r.paginas[estado.pagina]);
    $("resultado").scrollIntoView({ block: "start" });
  }

  function pintarPagina(p) {
    const lienzo = $("documento-lienzo");
    lienzo.innerHTML = "";
    if (p.vista_previa) {
      const img = document.createElement("img");
      img.src = p.vista_previa.imagen;
      img.alt = `Página ${p.numero} del documento`;
      lienzo.appendChild(img);
    }
    const errorPagina = $("pagina-error");
    const tbody = $("campos");
    tbody.innerHTML = "";
    $("avisos").innerHTML = "";
    if (p.estado !== "ok") {
      errorPagina.hidden = false;
      errorPagina.textContent = p.error || "No se pudo leer esta página.";
      $("cuadre").hidden = true;
      return;
    }
    errorPagina.hidden = true;

    p.campos.forEach((c) => {
      const fila = document.createElement("tr");
      fila.dataset.campo = c.clave;
      const vacio = c.valor === null;
      const iso = c.normalizado && c.normalizado !== c.valor && !String(c.normalizado).startsWith("AMBIGUOUS") ? c.normalizado : null;
      const alertas = c.alertas.map((a) => `<span class="alerta-campo ${a.nivel === "info" ? "alerta-campo--info" : ""}">${escapar(a.texto)}</span>`).join("");
      fila.innerHTML = `
        <td><span class="campo__nombre">${escapar(c.nombre)}</span>
          ${c.evidencia && c.evidencia.texto ? `<span class="campo__origen">Leído en: «${escapar(c.evidencia.texto)}»</span>` : ""}</td>
        <td><span class="valor ${vacio ? "valor--vacio" : ""}">${vacio ? "No detectado: digítalo desde el documento" : escapar(c.valor)}</span>
          ${iso ? `<span class="valor__iso">${c.clave === "date" ? "Formato ISO" : "Normalizado"}: ${escapar(iso)}</span>` : ""}${alertas}</td>
        <td><span class="sello sello--${c.confianza}">${CONFIANZA[c.confianza] || c.confianza}</span>
          ${vacio ? "" : `<span class="sello__detalle">${c.vistas} de ${c.de} lecturas</span>`}</td>`;
      if (c.evidencia && p.vista_previa) {
        fila.classList.add("con-caja");
        fila.tabIndex = 0;
        const caja = dibujarCaja(lienzo, c, p.vista_previa);
        const encender = (si) => { caja.classList.toggle("resaltada", si); fila.classList.toggle("resaltada", si); };
        fila.addEventListener("mouseenter", () => encender(true));
        fila.addEventListener("mouseleave", () => encender(false));
        fila.addEventListener("focus", () => encender(true));
        fila.addEventListener("blur", () => encender(false));
        caja.addEventListener("mouseenter", () => encender(true));
        caja.addEventListener("mouseleave", () => encender(false));
      }
      tbody.appendChild(fila);
    });

    const cuadre = $("cuadre");
    cuadre.hidden = !p.cuadre;
    if (p.cuadre) {
      cuadre.className = `cuadre cuadre--${p.cuadre.nivel}`;
      cuadre.textContent = (p.cuadre.nivel === "ok" ? "✓ " : "") + p.cuadre.texto;
    }
    const avisos = [...(p.avisos || []), ...(p.alertas || []).map((a) => a.texto)];
    avisos.forEach((t) => {
      const parrafo = document.createElement("p");
      parrafo.textContent = t;
      $("avisos").appendChild(parrafo);
    });
  }

  function dibujarCaja(lienzo, campo, vista) {
    const [x0, y0, x1, y1] = campo.evidencia.caja;
    const margen = 6;
    const caja = document.createElement("div");
    caja.className = "caja";
    caja.style.left = `${Math.max(0, (x0 - margen) / vista.ancho * 100)}%`;
    caja.style.top = `${Math.max(0, (y0 - margen) / vista.alto * 100)}%`;
    caja.style.width = `${(x1 - x0 + 2 * margen) / vista.ancho * 100}%`;
    caja.style.height = `${(y1 - y0 + 2 * margen) / vista.alto * 100}%`;
    caja.innerHTML = `<span>${CORTO[campo.clave] || campo.clave}</span>`;
    caja.title = `${campo.nombre}: ${campo.valor}`;
    lienzo.appendChild(caja);
    return caja;
  }

  function escapar(texto) {
    return String(texto).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---------- descargas (se generan en el navegador; el servidor no guarda nada) ----------
  function descargar(nombre, contenido, tipo) {
    const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
    const a = document.createElement("a");
    a.href = url; a.download = nombre; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function baseNombre() { return (estado.respuesta.archivo || "documento").replace(/\.[^.]+$/, ""); }

  $("descargar-json").addEventListener("click", () => {
    const r = estado.respuesta;
    const limpio = {
      archivo: r.archivo, estado: r.estado, segundos: r.segundos,
      paginas: r.paginas.map((p) => ({
        pagina: p.numero, estado: p.estado, error: p.error || null, cuadre: p.cuadre ? p.cuadre.estado : null,
        campos: Object.fromEntries((p.campos || []).map((c) => [c.clave, { valor: c.valor, normalizado: c.normalizado, confianza: c.confianza, alertas: c.alertas.map((a) => a.codigo) }])),
      })),
    };
    descargar(`${baseNombre()}_campos.json`, JSON.stringify(limpio, null, 2), "application/json");
  });

  $("descargar-csv").addEventListener("click", () => {
    const r = estado.respuesta;
    const claves = ["tax_id", "date", "document_number", "subtotal", "tax", "total"];
    const celda = (v) => (v === null || v === undefined ? "" : `"${String(v).replace(/"/g, '""')}"`);
    const filas = [["pagina", "estado", ...claves, ...claves.map((c) => `confianza_${c}`), "cuadre"].join(",")];
    r.paginas.forEach((p) => {
      const porClave = Object.fromEntries((p.campos || []).map((c) => [c.clave, c]));
      filas.push([p.numero, p.estado, ...claves.map((c) => celda(porClave[c] && porClave[c].valor)),
        ...claves.map((c) => celda(porClave[c] && porClave[c].confianza)), celda(p.cuadre && p.cuadre.estado)].join(","));
    });
    descargar(`${baseNombre()}_campos.csv`, "﻿" + filas.join("\r\n"), "text/csv");
  });

  // ---------- Cómo funciona ----------
  let acercaCargado = false;
  async function cargarAcerca() {
    if (acercaCargado) return;
    const contenedor = $("acerca");
    try {
      const respuesta = await fetch("/api/acerca");
      const info = await respuesta.json();
      contenedor.innerHTML = construirAcerca(info);
      acercaCargado = true;
    } catch (_e) {
      contenedor.innerHTML = '<p class="nota">No se pudo cargar la información del modelo.</p>';
    }
  }

  const cifra = (texto) => escapar(String(texto || "").split(" (")[0]);

  function construirAcerca(info) {
    const ev = info.evaluacion_final || {};
    const val = info.validacion || {};
    const filas = (lista) => lista.map((f) => `<tr><td>${escapar(f[0])}</td><td>${escapar(f[1])}</td></tr>`).join("");
    let html = `
      <h2>Qué hace</h2>
      <p>Lee la imagen o el PDF con Tesseract 5 en <strong>${info.vistas_ocr} versiones distintas de la misma página</strong> (original, ampliada, binarizada, con corrección de luz, con dos modelos de Tesseract y en español). Cada versión propone valores para los seis campos y el sistema se queda con el que más lecturas respaldan, comprobando además que subtotal + IVA = total.</p>
      <p>No inventa datos: si un valor no aparece leído en el documento, el campo queda vacío para que lo digites. Cada valor muestra dónde se leyó.</p>`;
    if (ev.exactitud_por_campo) {
      html += `
      <h2>Qué tan bien funciona</h2>
      <div class="metricas">
        <div class="metrica"><strong>${cifra(ev.exactitud_por_campo)}</strong><span>de los campos correctos en ${escapar(String(ev.campos_evaluados || ""))} campos de prueba (meta: 70 %)</span></div>
        <div class="metrica"><strong>${cifra(ev.exactitud_sroie)}</strong><span>en escaneos (SROIE)</span></div>
        <div class="metrica"><strong>${cifra(ev.exactitud_wildreceipt)}</strong><span>en fotos de celular (WildReceipt)</span></div>
        ${val.documentos_nuevos ? `<div class="metrica"><strong>${cifra(val.documentos_nuevos.exactitud)}</strong><span>en ${escapar(String(val.documentos_nuevos.documentos))} recibos que nunca se miraron al construir el modelo</span></div>` : ""}
      </div>
      <p class="nota">${escapar(ev.muestra || "")}</p>`;
    }
    if (val.escenarios && val.escenarios.length) {
      html += `<h2>Dónde falla</h2><p>Pruebas con imágenes degradadas a propósito (exactitud por campo):</p>
        <table class="tabla-simple"><thead><tr><th>Condición</th><th>Exactitud</th></tr></thead><tbody>${filas(val.escenarios)}</tbody></table>`;
    }
    html += `
      <h2>Cuándo no usarlo</h2>
      <ul>${(info.fuera_de_alcance || []).map((x) => `<li>${escapar(x.charAt(0).toUpperCase() + x.slice(1))}.</li>`).join("")}
        <li>Para aprobar pagos o declarar impuestos sin que una persona revise cada valor.</li></ul>
      <h2>Privacidad</h2>
      <p>El archivo se procesa en este servidor solo durante la lectura y se borra al terminar: no se guarda ni se envía a otros servicios. Las descargas CSV y JSON se generan en tu navegador e incluyen solo los campos, no el texto completo de la factura.</p>
      <p>Esta versión de demostración está alojada en Hugging Face, fuera de Ecuador. Para facturas con datos de terceros usa la versión local (instrucciones en el repositorio), que procesa todo en tu equipo.</p>
      <h2>Límites de esta versión</h2>
      <p>Imágenes JPG o PNG y PDF de hasta ${info.limites.tamano_maximo_mb} MB; los PDF, de hasta ${info.limites.paginas_maximas_pdf} páginas. Cada página se lee como un comprobante separado.</p>
      <p><a href="https://github.com/Jesusl2202/Document-Scanner">Código, datos, métricas y documentación del proyecto</a>.</p>`;
    return html;
  }
})();
