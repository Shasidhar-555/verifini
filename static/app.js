const $ = (id) => document.getElementById(id);
const form = $('post-form');
const imageInput = $('image-input');
let selectedImageDataUrl = null;
let lastAnalysis = null;
let toastTimer;

function showToast(message) {
  const toast = $('toast');
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 3000);
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function updateCounts() {
  $('caption-count').textContent = `${$('caption').value.length} / 500`;
  $('description-count').textContent = `${$('description').value.length} / 1500`;
}
$('caption').addEventListener('input', updateCounts);
$('description').addEventListener('input', updateCounts);

imageInput.addEventListener('change', () => {
  const file = imageInput.files?.[0];
  $('form-error').hidden = true;
  if (!file) {
    selectedImageDataUrl = null;
    $('image-preview').hidden = true;
    $('upload-box').classList.remove('has-image');
    $('upload-title').textContent = 'Choose an image to review';
    $('upload-hint').textContent = 'PNG, JPG or WEBP · up to 8 MB';
    return;
  }
  if (!file.type.startsWith('image/')) {
    showError('Please choose an image file.'); imageInput.value = ''; return;
  }
  if (file.size > 8 * 1024 * 1024) {
    showError('Image is too large. Choose a file smaller than 8 MB.'); imageInput.value = ''; return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    selectedImageDataUrl = reader.result;
    $('image-preview').src = reader.result;
    $('image-preview').hidden = false;
    $('upload-box').classList.add('has-image');
    $('upload-title').textContent = file.name;
    $('upload-hint').textContent = 'Image selected · click to replace';
  };
  reader.readAsDataURL(file);
});
function showError(message) {
  $('form-error').textContent = message;
  $('form-error').hidden = false;
}
function setView(view) {
  $('empty-state').hidden = view !== 'empty';
  $('loading-state').hidden = view !== 'loading';
  $('results-content').hidden = view !== 'results';
}
function verdictClass(verdict) {
  if (verdict === 'Possible misleading context') return 'warning';
  if (verdict === 'Needs verification') return 'needs';
  if (verdict === 'Related content found') return 'related';
  return 'clear';
}
function verdictIcon(verdict) {
  if (verdict === 'Possible misleading context' || verdict === 'Needs verification') {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 21 19H3L12 3Z"/><path d="M12 9v4m0 3h.01"/></svg>';
  }
  if (verdict === 'Related content found') {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 4 4"/></svg>';
  }
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5m0 4h.01"/></svg>';
}
function renderAnalysis(result) {
  lastAnalysis = result;
  const klass = verdictClass(result.verdict);
  $('verdict-card').className = `verdict-card ${klass}`;
  $('verdict-icon').innerHTML = verdictIcon(result.verdict);
  $('verdict-title').textContent = result.verdict;
  $('confidence-label').textContent = `${String(result.confidence || 'Low').toUpperCase()} CONFIDENCE`;
  $('verdict-summary').textContent = result.summary || '';
  $('reason-count').textContent = `${(result.reasons || []).length} finding${(result.reasons || []).length === 1 ? '' : 's'}`;
  $('reasons-list').innerHTML = (result.reasons || []).map(r => `<li>${escapeHtml(r)}</li>`).join('') || '<li>No specific flags were detected.</li>';
  const evidence = result.evidence || [];
  $('evidence-count').textContent = `${evidence.length} record${evidence.length === 1 ? '' : 's'}`;
  $('no-evidence').hidden = evidence.length > 0;
  $('evidence-list').innerHTML = evidence.map(item => {
    const image = item.image_url ? `<img class="evidence-thumb" src="${escapeHtml(item.image_url)}" alt="Sample evidence image" />` : '<div class="evidence-thumb placeholder"><svg viewBox="0 0 24 24"><path d="M4 5h16v14H4zM8 9h8M8 13h5"/></svg></div>';
    const source = item.source_url && /^https?:\/\//i.test(item.source_url) ? `<a class="evidence-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>` : '<span class="evidence-link">No external source link supplied</span>';
    const match = item.match_type === 'image' ? `Image hash distance: ${item.hash_distance}/64` : `Text similarity: ${item.similarity ?? 'n/a'}`;
    return `<article class="evidence-card">${image}<div><span class="sample-tag">${item.is_sample ? 'SAMPLE DATA' : 'INDEXED RECORD'}</span><h4 class="evidence-title">${escapeHtml(item.id)} · ${escapeHtml(item.claim_text || 'Related record')}</h4><div class="evidence-meta"><span>${escapeHtml(item.recorded_date || 'Date not recorded')}</span><span>·</span><span>${escapeHtml(item.location || 'Location not recorded')}</span></div><p class="evidence-description">${escapeHtml(item.source_name || 'Source not recorded')} · ${escapeHtml(match)}</p>${source}</div></article>`;
  }).join('');
  $('suggested-caption').textContent = result.suggested_caption || $('caption').value || 'No suggested wording available.';
  $('disclaimer-text').textContent = result.disclaimer || 'This prototype checks a local evidence index only. No match does not mean authentic.';
  $('challenge-message').hidden = true;
  setView('results');
  $('results-panel').scrollIntoView({behavior:'smooth', block:'nearest'});
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  $('form-error').hidden = true;
  const caption = $('caption').value.trim();
  const description = $('description').value.trim();
  const file = imageInput.files?.[0];
  if (!caption && !description && !file) {
    showError('Add an image, caption, or description before checking.'); return;
  }
  const body = new FormData();
  body.append('caption', caption);
  body.append('description', description);
  if (file) body.append('image', file);
  $('check-button').disabled = true;
  $('check-button').querySelector('span:nth-child(2)').textContent = 'Checking…';
  setView('loading');
  try {
    const response = await fetch('/analyze', {method:'POST', body});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to analyze this post.');
    renderAnalysis(data);
  } catch (error) {
    setView('empty');
    showError(`${error.message || 'Something went wrong.'} Check that the VerifINI server is running and try again.`);
  } finally {
    $('check-button').disabled = false;
    $('check-button').querySelector('span:nth-child(2)').textContent = 'Check Before Posting';
  }
});

$('use-suggestion').addEventListener('click', () => {
  if (!lastAnalysis) return;
  $('caption').value = lastAnalysis.suggested_caption || $('caption').value;
  updateCounts();
  $('caption').focus();
  showToast('Suggested wording copied into your caption. Review it before publishing.');
});
$('edit-button').addEventListener('click', () => {
  $('caption').focus();
  $('composer').scrollIntoView({behavior:'smooth', block:'start'});
});
$('publish-button').addEventListener('click', async () => {
  const payload = {
    caption: $('caption').value.trim(),
    description: $('description').value.trim(),
    image_url: selectedImageDataUrl,
    analysis: lastAnalysis || {}
  };
  $('publish-button').disabled = true;
  try {
    const response = await fetch('/publish', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Unable to publish.');
    showToast('Your post has been published to the VerifINI demo feed.');
    form.reset(); selectedImageDataUrl = null; lastAnalysis = null; updateCounts();
    $('image-preview').hidden = true; $('upload-box').classList.remove('has-image');
    $('upload-title').textContent = 'Choose an image to review'; $('upload-hint').textContent = 'PNG, JPG or WEBP · up to 8 MB';
    setView('empty');
    await loadFeed();
    $('feed-section').scrollIntoView({behavior:'smooth', block:'start'});
  } catch (error) { showToast(error.message || 'Unable to publish.'); }
  finally { $('publish-button').disabled = false; }
});
$('challenge-button').addEventListener('click', async () => {
  try {
    const response = await fetch('/challenge', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({feedback:'User requested a review of the displayed analysis.'})});
    if (!response.ok) throw new Error('Could not record feedback.');
    $('challenge-message').textContent = 'Feedback recorded for this prototype.';
    $('challenge-message').hidden = false;
  } catch { showToast('Could not record feedback. Is the server running?'); }
});

function formatDate(value) {
  if (!value) return 'Just now';
  try { return new Date(value).toLocaleString(undefined, {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'}); }
  catch { return value; }
}
function renderPost(post) {
  const analysis = post.analysis || {};
  const status = analysis.verdict || 'Not checked';
  const klass = status === 'Possible misleading context' ? 'warning' : status === 'Needs verification' ? 'info' : '';
  const image = post.image_url ? `<img class="post-image" src="${escapeHtml(post.image_url)}" alt="Image attached to post" />` : '';
  return `<article class="post-card">${image}<div class="post-content"><div class="post-topline"><div class="post-author"><span class="avatar">V</span><span>VerifINI member</span></div><span class="post-time">${escapeHtml(formatDate(post.published_at))}</span></div>${post.caption ? `<p class="post-caption">${escapeHtml(post.caption)}</p>` : ''}${post.description ? `<p class="post-description">${escapeHtml(post.description)}</p>` : ''}<div class="post-footer"><span class="post-status ${klass}"><svg viewBox="0 0 16 16"><path d="m3 8 3 3 7-7"/></svg> Reviewed: ${escapeHtml(status)}</span><span class="post-likes">Demo post</span></div></div></article>`;
}
async function loadFeed() {
  try {
    const response = await fetch('/feed');
    if (!response.ok) throw new Error('Feed request failed');
    const posts = await response.json();
    $('feed-count').textContent = `${posts.length} post${posts.length === 1 ? '' : 's'}`;
    $('feed-list').innerHTML = posts.length ? posts.map(renderPost).join('') : '<div class="feed-empty"><span class="feed-empty-icon"><svg viewBox="0 0 24 24"><path d="M4 5.5h16v13H4zM8 9h8M8 13h5"/></svg></span><span><strong>Your feed is ready</strong><small>Publish your first reviewed post to see it here.</small></span></div>';
  } catch { $('feed-list').innerHTML = '<div class="feed-empty"><span><strong>Feed is unavailable</strong><small>Check that the local server is running.</small></span></div>'; }
}
updateCounts();
loadFeed();
