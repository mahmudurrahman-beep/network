// CSRF Token Helper
function getCsrfToken() {
  const token = document.querySelector('[name=csrfmiddlewaretoken]');
  if (!token) {
    console.error('CSRF token not found!');
    return '';
  }
  return token.value;
}

// Follow / Unfollow - FIXED VERSION
const followBtn = document.getElementById('follow-btn');
if (followBtn) {
  followBtn.addEventListener('click', () => {
    const username = followBtn.dataset.username;
    const csrfToken = getCsrfToken();

    if (!csrfToken) {
      alert('CSRF token missing. Reload the page.');
      return;
    }

    // Immediate UI feedback
    followBtn.disabled = true;
    const originalText = followBtn.textContent;
    followBtn.textContent = '...';

    fetch(`/toggle-follow/${username}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
      },
      credentials: 'same-origin'
    })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(data => {
        // Remove ALL button styling classes
        const buttonClasses = ['btn-primary', 'btn-outline-primary', 'btn-secondary', 
                               'btn-outline-secondary', 'btn-success', 'btn-danger',
                               'btn-warning', 'btn-info', 'btn-light', 'btn-dark',
                               'btn-following', 'btn-not-following'];
        
        buttonClasses.forEach(cls => followBtn.classList.remove(cls));
        
        // Add base button class
        followBtn.classList.add('btn');
        
        // Apply correct state
        if (data.action === 'followed') {
          followBtn.textContent = 'Unfollow';
          followBtn.classList.add('btn-following');
        } else {
          followBtn.textContent = 'Follow';
          followBtn.classList.add('btn-not-following');
        }

        // Update follower counts
        const followersEl = document.querySelector('[data-followers-count]');
        if (followersEl) {
          const followersLink = followersEl.querySelector('a');
          if (followersLink) followersLink.textContent = `${data.followers} followers`;
        }

        const followingEl = document.querySelector('#following-count');
        if (followingEl && data.following !== undefined) {
          const followingLink = followingEl.querySelector('a');
          if (followingLink) followingLink.textContent = `${data.following} following`;
        }
      })
      .catch(error => {
        console.error('Follow failed:', error);
        alert('Could not follow/unfollow. Please try again.');
      })
      .finally(() => {
        followBtn.disabled = false;
      });
  });
} 

// Edit Post
document.querySelectorAll('.edit-post').forEach(btn => {
  btn.addEventListener('click', function () {
    const postId = btn.dataset.post;
    const postCard = btn.closest('.post-card');
    if (!postCard) return;

    const contentDiv = postCard.querySelector('.post-content');
    if (!contentDiv) return;

    const postText = contentDiv.querySelector('.post-text');
    if (!postText) return;

    const originalText = postText.innerText.trim();
    const originalHTML = contentDiv.innerHTML;

    const textarea = document.createElement('textarea');
    textarea.className = 'form-control mb-2';
    textarea.value = originalText;
    textarea.rows = 5;

    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-primary btn-sm mr-2';  // FIXED: me-2 → mr-2
    saveBtn.textContent = 'Save';

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-outline-secondary btn-sm';
    cancelBtn.textContent = 'Cancel';

    contentDiv.innerHTML = '';
    contentDiv.appendChild(textarea);
    contentDiv.appendChild(saveBtn);
    contentDiv.appendChild(cancelBtn);

    btn.style.display = 'none';

    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(0, 0);
    }, 50);

    saveBtn.onclick = () => {
      const newContent = textarea.value.trim();
      if (!newContent) return alert('Post cannot be empty');

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      fetch(`/edit-post/${postId}/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ content: newContent })
      })
        .then(response => {
          if (!response.ok) {
            return response.text().then(text => { throw new Error(text); });
          }
          return response.json();
        })
        .then(() => {
          const newText = document.createElement('p');
          newText.className = 'post-text mb-0';
          newText.innerHTML = newContent.replace(/\n/g, '<br>');
          contentDiv.innerHTML = '';
          contentDiv.appendChild(newText);
          btn.style.display = 'inline-block';
        })
        .catch(error => {
          alert(`Failed to save: ${error.message}`);
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save';
        });
    };

    cancelBtn.onclick = () => {
      contentDiv.innerHTML = originalHTML;
      btn.style.display = 'inline-block';
    };
  });
});

// Like / Unlike - UPDATED TO MATCH SERVER RESPONSE
document.querySelectorAll('.thumbs-up, .thumbs-down').forEach(btn => {
  btn.addEventListener('click', function() {
    const postId = this.dataset.post;
    const value = parseInt(this.dataset.value);

    const upBtn = document.querySelector(`.thumbs-up[data-post="${postId}"]`);
    const downBtn = document.querySelector(`.thumbs-down[data-post="${postId}"]`);
    
    if (!upBtn || !downBtn) return;
    
    const upSpan = upBtn.querySelector('span');
    const downSpan = downBtn.querySelector('span');

    // Disable buttons during request
    upBtn.disabled = true;
    downBtn.disabled = true;

    fetch(`/vote/${postId}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({ value })
    })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP error ${response.status}`);
        return response.json();
      })
      .then(data => {
        console.log('SERVER VOTE DATA:', data);
        
        // Update counts from server
        upSpan.textContent = data.up || 0;
        downSpan.textContent = data.down || 0;

        // Update button states from server
        const allClasses = ['btn-primary', 'btn-outline-primary', 'btn-secondary', 
                          'btn-outline-secondary', 'btn-success', 'btn-outline-success',
                          'btn-danger', 'btn-outline-danger', 'btn-warning', 'btn-info',
                          'btn-light', 'btn-dark', 'btn-link'];
        
        allClasses.forEach(cls => {
          upBtn.classList.remove(cls);
          downBtn.classList.remove(cls);
        });

        upBtn.classList.add('btn', 'btn-sm');
        downBtn.classList.add('btn', 'btn-sm');

        // Use server's user_up/user_down values
        if (data.user_up === true) {
          upBtn.classList.add('btn-success');
          downBtn.classList.add('btn-outline-secondary');
        } else if (data.user_down === true) {
          upBtn.classList.add('btn-outline-secondary');
          downBtn.classList.add('btn-danger');
        } else {
          upBtn.classList.add('btn-outline-secondary');
          downBtn.classList.add('btn-outline-secondary');
        }
      })
      .catch(err => {
        console.error('Vote failed:', err);
        alert('Failed to update vote. Please try again.');
      })
      .finally(() => {
        upBtn.disabled = false;
        downBtn.disabled = false;
      });
  });
}); 

// New Post Submission
const newPostForm = document.getElementById('new-post-form');
if (newPostForm) {
  newPostForm.addEventListener('submit', function (e) {
    e.preventDefault();

    const formData = new FormData(this);
    const messageDiv = document.getElementById('post-message');

    if (messageDiv) {
      messageDiv.classList.remove('d-none', 'alert-success', 'alert-danger');
      messageDiv.classList.add('alert-info');
      messageDiv.textContent = 'Posting...';
    }

    fetch('/new-post/', {
      method: 'POST',
      body: formData,
      headers: { 'X-CSRFToken': getCsrfToken() }
    })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          if (messageDiv) {
            messageDiv.classList.remove('alert-info');
            messageDiv.classList.add('alert-danger');
            messageDiv.textContent = data.error;
          }
        } else {
          if (messageDiv) {
            messageDiv.classList.remove('alert-info');
            messageDiv.classList.add('alert-success');
            messageDiv.textContent = 'Posted successfully!';
          }
          newPostForm.reset();
          setTimeout(() => location.reload(), 1500);
        }
      })
      .catch(error => {
        console.error('Post error:', error);
        if (messageDiv) {
          messageDiv.classList.remove('alert-info');
          messageDiv.classList.add('alert-danger');
          messageDiv.textContent = 'Failed to post. Try again.';
        }
      });
  });
}

// Delete Post
document.querySelectorAll('.delete-post').forEach(btn => {
  btn.addEventListener('click', function () {
    if (!confirm('Are you sure you want to delete this post?')) return;

    const postId = this.dataset.post;
    const postCard = this.closest('.post-card');
    if (!postCard) return;

    fetch(`/delete-post/${postId}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() }
    })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP error ${response.status}`);
        return response.json();
      })
      .then(data => {
        if (data.message) {
          postCard.remove();
          alert('Post deleted successfully');
        } else {
          alert('Failed to delete post');
        }
      })
      .catch(error => {
        console.error('Delete failed:', error);
        alert('Error deleting post. Check console for details.');
      });
  });
});

// Delete Message
document.querySelectorAll('.delete-message').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!confirm('Delete this message?')) return;

    const messageId = btn.dataset.messageId;
    const messageItem = btn.closest('.message-item');

    fetch(`/delete-message/${messageId}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() }
    })
      .then(r => r.json())
      .then(data => {
        if (data.message) messageItem.remove();
      })
      .catch(err => console.error('Delete message failed:', err));
  });
});

// Hide/Delete Conversation
document.querySelectorAll('.delete-conversation').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!confirm('Clear this conversation for you? (The other user will still see their messages)')) return;

    const username = btn.dataset.other;
    const csrfToken = getCsrfToken();

    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = 'Clearing...';

    fetch(`/delete-conversation/${username}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      credentials: 'same-origin'
    })
      .then(response => {
        if (!response.ok) throw new Error('Network error');
        return response.json();
      })
      .then(data => {
        alert(data.message || 'Conversation cleared for you!');
        window.location.href = '/messages/';
      })
      .catch(error => {
        console.error('Clear conversation failed:', error);
        alert('Failed to clear conversation.');
        btn.disabled = false;
        btn.textContent = originalText;
      });
  });
});

// Time ago display
document.querySelectorAll('.time-ago').forEach(el => {
  const timestamp = new Date(el.dataset.timestamp);
  const now = new Date();
  const diff = Math.floor((now - timestamp) / 1000);

  let text = '';
  if (diff < 60) text = 'just now';
  else if (diff < 3600) text = `${Math.floor(diff / 60)} minutes ago`;
  else if (diff < 86400) text = `${Math.floor(diff / 3600)} hours ago`;
  else text = `${Math.floor(diff / 86400)} days ago`;

  el.textContent = text;
});

// Hover timestamp
document.querySelectorAll('.message-item').forEach(item => {
  const timeEl = item.querySelector('.time-ago');
  if (timeEl) {
    const fullTime = new Date(timeEl.dataset.timestamp).toLocaleString();
    timeEl.title = fullTime;
  }
});

// =========================================================
// COMMENTS UX + ACTIONS (single delegated handler)
// - Show/Hide comments
// - Show/Hide replies
// - Reply form toggle + cancel
// - Delete comment (pessimistic)
// - Edit comment (works for replies too)
// =========================================================
document.addEventListener('click', function (e) {
  // Show/Hide comments for a post
  const commentsBtn = e.target.closest('.js-toggle-comments');
  if (commentsBtn) {
    const postId = commentsBtn.dataset.postId;
    const body = document.querySelector(`.js-comments-body[data-post-id="${postId}"]`);
    if (!body) return;

    const isHidden = body.classList.contains('d-none');
    body.classList.toggle('d-none');

    commentsBtn.textContent = isHidden ? 'Hide comments' : 'Show comments';
    commentsBtn.setAttribute('aria-expanded', isHidden ? 'true' : 'false');
    return;
  }

  // Show/Hide replies under a root comment
  const repliesBtn = e.target.closest('.js-toggle-replies');
  if (repliesBtn) {
    const commentId = repliesBtn.dataset.commentId;
    const box = document.querySelector(`.js-replies[data-parent-id="${commentId}"]`);
    if (!box) return;

    const count = repliesBtn.dataset.count;
    const isHidden = box.classList.contains('d-none');
    box.classList.toggle('d-none');

    const suffix = count ? ` (${count})` : '';
    repliesBtn.textContent = isHidden ? `Hide replies${suffix}` : `Show replies${suffix}`;
    repliesBtn.setAttribute('aria-expanded', isHidden ? 'true' : 'false');
    return;
  }

  // Reply button -> toggle reply form (only exists for root comments in your template)
  const replyBtn = e.target.closest('.reply-btn');
  if (replyBtn) {
    e.preventDefault();
    const commentId = replyBtn.dataset.commentId;

    const container = replyBtn.closest('.comment-item, .reply-item, .comment-content, .reply-content');
    const form = container ? container.querySelector(`.reply-form[data-parent-id="${commentId}"]`) : null;

    if (!form) {
      console.error('Reply form not found for comment:', commentId);
      return;
    }

    const wasHidden = form.classList.contains('d-none');
    form.classList.toggle('d-none');

    if (wasHidden) {
      const textarea = form.querySelector('textarea');
      if (textarea) {
        setTimeout(() => {
          textarea.focus();
          form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
      }
    }
    return;
  }

  // Cancel reply
  const cancelReply = e.target.closest('.cancel-reply');
  if (cancelReply) {
    const form = cancelReply.closest('.reply-form');
    if (form) form.classList.add('d-none');
    return;
  }

  // Delete comment (pessimistic)
  const delBtn = e.target.closest('.delete-comment');
  if (delBtn && !delBtn.disabled) {
    if (!confirm('Delete this comment?')) return;

    const commentId = delBtn.dataset.commentId;
    const commentItem = delBtn.closest('.comment-item, .reply-item');
    if (!commentItem) return;

    delBtn.disabled = true;
    const originalHTML = delBtn.innerHTML;
    delBtn.innerHTML = '<span class="spinner-border spinner-border-sm mr-1"></span> Deleting...'; // FIXED: me-1 → mr-1

    fetch(`/delete-comment/${commentId}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'same-origin'
    })
      .then(response => response.json().then(data => ({ ok: response.ok, data })))
      .then(({ ok, data }) => {
        if (ok && (data.status === 'success' || data.message)) {
          commentItem.style.transition = 'opacity 0.45s ease, transform 0.25s ease';
          commentItem.style.opacity = '0';
          commentItem.style.transform = 'translateY(-6px)';
          setTimeout(() => commentItem.remove(), 450);
        } else {
          throw new Error(data.message || data.error || 'Delete rejected');
        }
      })
      .catch(err => {
        console.error('Delete failed:', err);
        delBtn.disabled = false;
        delBtn.innerHTML = originalHTML;
        alert('Failed to delete: ' + err.message);
      });

    return;
  }

  // Edit comment (delegated so it still works after DOM changes)
  const editBtn = e.target.closest('.edit-comment');
  if (editBtn) {
    const commentId = editBtn.dataset.commentId;
    const commentItem = editBtn.closest('.comment-item, .reply-item');
    if (!commentItem) return;

    const textDiv = commentItem.querySelector('.comment-text');
    const form = commentItem.querySelector('.edit-form');
    const textarea = commentItem.querySelector('.edit-textarea');
    const saveBtn = commentItem.querySelector('.save-edit');
    const cancelBtn = commentItem.querySelector('.cancel-edit');

    if (!textDiv || !form || !textarea || !saveBtn || !cancelBtn) return;

    const originalText = textDiv.innerText.trim();

    form.classList.remove('d-none');
    textarea.value = originalText;
    textarea.focus();

    textDiv.style.display = 'none';
    editBtn.style.display = 'none';

    saveBtn.onclick = () => {
      const newContent = textarea.value.trim();
      if (!newContent) return alert('Comment cannot be empty');

      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      fetch(`/edit-comment/${commentId}/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ content: newContent })
      })
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
          if (ok && data.message) {
            textDiv.innerHTML = newContent.replace(/\n/g, '<br>');
            textDiv.style.display = 'block';
            form.classList.add('d-none');
            editBtn.style.display = 'inline-block';
          } else {
            throw new Error(data.error || data.message || 'Update failed');
          }
        })
        .catch(err => {
          alert('Failed to update: ' + err.message);
        })
        .finally(() => {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save';
        });
    };

    cancelBtn.onclick = () => {
      textDiv.style.display = 'block';
      form.classList.add('d-none');
      editBtn.style.display = 'inline-block';
    };

    return;
  }
});

// Auto-dismiss Django flash messages (e.g., "Comment added!")
(function () {
  function closeAlert(el) {
    // Prefer Bootstrap 4's JS plugin if present
    if (window.jQuery && typeof window.jQuery(el).alert === "function") {
      window.jQuery(el).alert("close");
      return;
    }
    // Fallback: fade + remove
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }

  function autoDismiss() {
    const isMobile = window.matchMedia("(max-width: 576px)").matches;
    const delay = isMobile ? 2200 : 3000;

    document.querySelectorAll(".messages .alert.alert-dismissible").forEach((el) => {
      // Avoid double timers
      if (el.dataset.autodismissed) return;
      el.dataset.autodismissed = "1";
      setTimeout(() => closeAlert(el), delay);
    });
  }

  document.addEventListener("DOMContentLoaded", autoDismiss);
})();

// =========================================================
// Action menu (⋮) toggle for Post/Comment actions
// - Works with server-rendered menus
// - Doesn't break existing edit/delete handlers
// =========================================================
(function () {
  function closeAllMenus(exceptMenu) {
    document.querySelectorAll('.action-menu-dropdown.show').forEach(menu => {
      if (exceptMenu && menu === exceptMenu) return;
      menu.classList.remove('show');
      menu.setAttribute('aria-hidden', 'true');
      const toggle = menu.closest('.action-menu')?.querySelector('.js-action-menu-toggle');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    });
  }

  document.addEventListener('click', function (e) {
    const toggle = e.target.closest('.js-action-menu-toggle');

    if (toggle) {
      e.preventDefault();
      e.stopPropagation();

      const wrapper = toggle.closest('.action-menu');
      if (!wrapper) return;

      const menu = wrapper.querySelector('.js-action-menu');
      if (!menu) return;

      const isOpen = menu.classList.contains('show');

      // close others first
      closeAllMenus(menu);

      // toggle this one
      if (isOpen) {
        menu.classList.remove('show');
        menu.setAttribute('aria-hidden', 'true');
        toggle.setAttribute('aria-expanded', 'false');
      } else {
        menu.classList.add('show');
        menu.setAttribute('aria-hidden', 'false');
        toggle.setAttribute('aria-expanded', 'true');
      }
      return;
    }

    // click outside closes all
    closeAllMenus();
  });

  // Escape closes
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAllMenus();
  });
})();

// =========================================================
// Auto-hide success alerts (Comment added, etc.)
// =========================================================
(function () {
  setTimeout(() => {
    document.querySelectorAll('.alert-success, .comment-added-alert').forEach(el => {
      el.classList.add('fade');
      setTimeout(() => el.remove(), 600);
    });
  }, 3000);
})();
