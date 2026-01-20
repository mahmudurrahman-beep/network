// CSRF Token Helper
function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!token) {
        console.error('CSRF token not found!');
        return '';
    }
    return token.value;
}

// Follow / Unfollow + LIVE follower count update
const followBtn = document.getElementById('follow-btn');
if (followBtn) {
    followBtn.addEventListener('click', () => {
        const username = followBtn.dataset.username;
        const csrfToken = getCsrfToken();

        if (!csrfToken) {
            alert('CSRF token missing. Reload the page.');
            return;
        }

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
            followBtn.textContent = data.action === 'followed' ? 'Unfollow' : 'Follow';
            followBtn.classList.toggle('btn-primary', data.action === 'followed');
            followBtn.classList.toggle('btn-outline-primary', data.action !== 'followed');

            const followersEl = document.querySelector('[data-followers-count]');
            if (followersEl) {
                const followersLink = followersEl.querySelector('a');
                if (followersLink) {
                    followersLink.textContent = `${data.followers} followers`;
                }
            }

            const followingEl = document.querySelector('#following-count');
            if (followingEl && data.following !== undefined) {
                const followingLink = followingEl.querySelector('a');
                if (followingLink) {
                    followingLink.textContent = `${data.following} following`;
                }
            }
        })
        .catch(error => {
            console.error('Follow failed:', error);
            alert('Could not follow/unfollow. Please try again.');
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
        saveBtn.className = 'btn btn-primary btn-sm me-2';
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
            .then(data => {
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

// Like / Unlike
document.querySelectorAll('.thumbs-up, .thumbs-down').forEach(btn => {
    btn.addEventListener('click', () => {
        const postId = btn.dataset.post;
        const value = parseInt(btn.dataset.value);

        const upBtn = document.querySelector(`.thumbs-up[data-post="${postId}"]`);
        const downBtn = document.querySelector(`.thumbs-down[data-post="${postId}"]`);
        const upSpan = upBtn.querySelector('span');
        const downSpan = downBtn.querySelector('span');

        btn.disabled = true;

        fetch(`/vote/${postId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ value })
        })
        .then(r => r.json())
        .then(data => {
            upSpan.textContent = data.up;
            downSpan.textContent = data.down;

            upBtn.classList.toggle('btn-primary', data.user_up);
            upBtn.classList.toggle('btn-outline-secondary', !data.user_up);
            downBtn.classList.toggle('btn-danger', data.user_down);
            downBtn.classList.toggle('btn-outline-secondary', !data.user_down);
        })
        .catch(err => {
            console.error('Vote failed:', err);
            alert('Failed to update vote');
        })
        .finally(() => btn.disabled = false);
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
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
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
        if (!confirm('Are you sure you want to delete this post?')) {
            return;
        }

        const postId = this.dataset.post;
        const postCard = this.closest('.post-card');

        if (!postCard) return;

        fetch(`/delete-post/${postId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
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
            if (data.message) {
                messageItem.remove();
            }
        })
        .catch(err => console.error('Delete message failed:', err));
    });
});

// Hide/Delete Conversation
document.querySelectorAll('.delete-conversation').forEach(btn => {
    btn.addEventListener('click', () => {
        if (!confirm('Clear this conversation for you? (The other user will still see their messages)')) {
            return;
        }

        const username = btn.dataset.other;
        const csrfToken = getCsrfToken();

        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = 'Clearing...';

        fetch(`/delete-conversation/${username}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
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

// COMMENT FUNCTIONALITY - Reply Form Toggle and Delete
document.addEventListener('click', function(e) {
    // Reply button click - check multiple ways
    const replyBtn = e.target.closest('.reply-btn');
    if (replyBtn) {
        e.preventDefault();
        e.stopPropagation();
        
        const commentId = replyBtn.dataset.commentId;
        console.log('Reply button clicked for comment:', commentId);
        
        // Find the form in the same comment container
        const commentContainer = replyBtn.closest('.comment-item, .reply-item, .comment-content, .reply-content');
        const form = commentContainer ? commentContainer.querySelector(`.reply-form[data-parent-id="${commentId}"]`) : null;
        
        console.log('Form found:', form);
        
        if (form) {
            const isHidden = form.classList.contains('d-none');
            form.classList.toggle('d-none');
            
            if (isHidden) {
                const textarea = form.querySelector('textarea');
                if (textarea) {
                    setTimeout(() => {
                        textarea.focus();
                        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }, 100);
                }
            }
        } else {
            console.error('Reply form not found for comment:', commentId);
        }
        return;
    }

    // Cancel reply button
    if (e.target.matches('.cancel-reply') || e.target.closest('.cancel-reply')) {
        const form = e.target.closest('.reply-form');
        if (form) form.classList.add('d-none');
    }

    // Delete comment
    if (e.target.matches('.delete-comment') || e.target.closest('.delete-comment')) {
        if (!confirm('Delete this comment?')) return;
        
        const btn = e.target.matches('.delete-comment') ? e.target : e.target.closest('.delete-comment');
        const commentId = btn.dataset.commentId;
        const commentItem = btn.closest('.comment-item, .reply-item');

        if (!commentItem) return;

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        fetch(`/delete-comment/${commentId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                commentItem.style.transition = 'opacity 0.3s ease, height 0.3s ease';
                commentItem.style.opacity = '0';
                commentItem.style.height = '0';
                commentItem.style.overflow = 'hidden';
                
                setTimeout(() => {
                    commentItem.remove();
                    
                    // Show success message
                    const alert = document.createElement('div');
                    alert.className = 'alert alert-success position-fixed top-0 end-0 m-3';
                    alert.style.zIndex = '9999';
                    alert.innerHTML = '<i class="bi bi-check-circle me-2"></i>Comment deleted successfully';
                    document.body.appendChild(alert);
                    
                    setTimeout(() => alert.remove(), 3000);
                }, 300);
            } else {
                throw new Error(data.message || 'Delete failed');
            }
        })
        .catch(error => {
            console.error('Delete comment failed:', error);
            alert('Failed to delete comment: ' + error.message);
            btn.disabled = false;
            btn.innerHTML = 'Delete';
        });
    }
});

// Delete Comment/Reply – Pessimistic: only remove if server confirms success
document.addEventListener('click', e => {
    const btn = e.target.closest('.delete-comment');
    if (!btn || btn.disabled) return;  // Ignore if disabled or not button

    if (!confirm('Delete this comment?')) return;

    const commentId = btn.dataset.commentId;
    const commentItem = btn.closest('.comment-item');
    if (!commentItem) return;

    // Lock button to prevent any double action
    btn.disabled = true;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Deleting...';

    fetch(`/delete-comment/${commentId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json().then(data => ({ok: response.ok, data})))
    .then(({ok, data}) => {
        if (ok && (data.status === 'success' || data.message)) {
            // Server confirmed: fade + remove
            commentItem.style.transition = 'opacity 0.5s ease, transform 0.3s ease';
            commentItem.style.opacity = '0';
            commentItem.style.transform = 'translateY(-10px)';
            setTimeout(() => commentItem.remove(), 500);
            console.log('Deleted successfully');
            // No success alert — clean UI
        } else {
            throw new Error(data.message || data.error || 'Delete rejected');
        }
    })
    .catch(err => {
        console.error('Delete failed:', err);
        // Revert button on any failure
        btn.disabled = false;
        btn.innerHTML = originalHTML;
        alert('Failed to delete: ' + err.message);
        // Comment stays visible
    });
});


// Edit Comment (prepopulated)
document.querySelectorAll('.edit-comment').forEach(btn => {
    btn.addEventListener('click', () => {
        const commentId = btn.dataset.commentId;
        const commentItem = btn.closest('.comment-item');
        const textDiv = commentItem.querySelector('.comment-text');
        const originalText = textDiv.innerText.trim();
        const textarea = commentItem.querySelector('.edit-textarea');
        const form = commentItem.querySelector('.edit-form');
        const saveBtn = commentItem.querySelector('.save-edit');
        const cancelBtn = commentItem.querySelector('.cancel-edit');
        
        form.classList.remove('d-none');
        textarea.value = originalText;
        textarea.focus();
        textDiv.style.display = 'none';
        btn.style.display = 'none';
        
        saveBtn.onclick = () => {
            const newContent = textarea.value.trim();
            if (!newContent) return alert('Comment cannot be empty');
            fetch(`/edit-comment/${commentId}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ content: newContent })
            })
            .then(r => r.json())
            .then(data => {
                if (data.message) {
                    textDiv.innerHTML = newContent.replace(/\n/g, '<br>');
                    textDiv.style.display = 'block';
                    form.classList.add('d-none');
                    btn.style.display = 'inline-block';
                    alert('Comment updated successfully');
                }
            })
            .catch(err => alert('Failed to update: ' + err.message));
        };
        
        cancelBtn.onclick = () => {
            textDiv.style.display = 'block';
            form.classList.add('d-none');
            btn.style.display = 'inline-block';
        };
    });
});