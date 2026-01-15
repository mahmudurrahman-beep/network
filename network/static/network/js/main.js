// CSRF Token Helper
function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!token) {
        console.error('CSRF token not found!');
        return '';
    }
    return token.value;
}

// 1. Follow / Unfollow + LIVE follower count update
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
            // Update button
            followBtn.textContent = data.action === 'followed' ? 'Unfollow' : 'Follow';
            followBtn.classList.toggle('btn-primary', data.action === 'followed');
            followBtn.classList.toggle('btn-outline-primary', data.action !== 'followed');

            // LIVE update followers count (required part)
            const followersEl = document.querySelector('[data-followers-count]');
            if (followersEl) {
                followersEl.textContent = data.followers;
            }

            // Optional: update following count too (if you added data-following-count)
            const followingEl = document.querySelector('[data-following-count]');
            if (followingEl && data.following !== undefined) {
                followingEl.textContent = data.following;
            }

            console.log('Follow success. New followers:', data.followers);
        })
        .catch(error => {
            console.error('Follow failed:', error);
            alert('Could not follow/unfollow. Please try again.');
        });
    });
}

// Edit Post – 100% reliable prepopulation + debug
document.querySelectorAll('.edit-post').forEach(btn => {
    btn.addEventListener('click', function () {
        console.log('[EDIT] 1. Button clicked. Post ID:', btn.dataset.post);

        const postId = btn.dataset.post;
        const postCard = btn.closest('.post-card');
        if (!postCard) return console.error('[EDIT] 2. No .post-card');

        const contentDiv = postCard.querySelector('.post-content');
        if (!contentDiv) return console.error('[EDIT] 3. No .post-content');

        const postText = contentDiv.querySelector('.post-text');
        if (!postText) return console.error('[EDIT] 4. No .post-text');

        // Step 5: Grab original text BEFORE changing anything
        const originalText = postText.innerText.trim();
        console.log('[EDIT] 5. Original text for textarea:', originalText || '(empty - check template)');

        // Backup original HTML for cancel
        const originalHTML = contentDiv.innerHTML;
        console.log('[EDIT] 6. Original HTML backup:', originalHTML);

        // Create textarea and SET VALUE FIRST
        const textarea = document.createElement('textarea');
        textarea.className = 'form-control mb-2';
        textarea.value = originalText; // Prepopulate here
        textarea.rows = 5;

        // NO placeholder when we have content
        if (originalText) {
            textarea.placeholder = ''; // clear if content exists
        } else {
            textarea.placeholder = 'Edit your post...';
        }

        // Save & Cancel buttons
        const saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn-primary btn-sm me-2';
        saveBtn.textContent = 'Save';

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn btn-outline-secondary btn-sm';
        cancelBtn.textContent = 'Cancel';

        // Clear contentDiv AFTER grabbing everything
        contentDiv.innerHTML = '';
        contentDiv.appendChild(textarea);
        contentDiv.appendChild(saveBtn);
        contentDiv.appendChild(cancelBtn);

        btn.style.display = 'none';

        // Force focus + small delay to ensure browser renders value
        setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(0, 0); // cursor at start
            console.log('[EDIT] 7. Textarea value after render:', textarea.value);
        }, 50);

        // Save handler
        saveBtn.onclick = () => {
            const newContent = textarea.value.trim();
            if (!newContent) return alert('Post cannot be empty');

            console.log('[EDIT] 8. Saving new content:', newContent);

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
                console.log('[EDIT] 9. Save status:', response.status);
                if (!response.ok) {
                    return response.text().then(text => { throw new Error(text); });
                }
                return response.json();
            })
            .then(data => {
                console.log('[EDIT] 10. Success:', data);

                const newText = document.createElement('p');
                newText.className = 'post-text mb-0';
                newText.innerHTML = newContent.replace(/\n/g, '<br>');
                contentDiv.innerHTML = '';
                contentDiv.appendChild(newText);

                btn.style.display = 'inline-block';
            })
            .catch(error => {
                console.error('[EDIT] 11. Failed:', error);
                alert(`Failed to save: ${error.message}`);
                saveBtn.disabled = false;
                saveBtn.textContent = 'Save';
            });
        };

        // Cancel – restore original HTML
        cancelBtn.onclick = () => {
            contentDiv.innerHTML = originalHTML;
            btn.style.display = 'inline-block';
            console.log('[EDIT] 12. Canceled – restored original');
        };
    });
});

// 3. Like / Unlike (thumbs toggle + live count)
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

// New Post Submission (async + nice feedback)
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

        fetch('/new-post', {
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

                // Optional: auto-refresh to show new post
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

// Delete Post (async, no reload)
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
                postCard.remove(); // Remove post from page instantly
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
                messageItem.remove(); // instant removal
            }
        })
        .catch(err => console.error('Delete message failed:', err));
    });
});

// Hide/Delete Conversation – "Delete for me only"
document.querySelectorAll('.delete-conversation').forEach(btn => {
    btn.addEventListener('click', () => {
        if (!confirm('Clear this conversation for you? (The other user will still see their messages)')) {
            return;
        }

        const username = btn.dataset.other;
        const csrfToken = getCsrfToken();

        // Optional: show loading state
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
            window.location.href = '/messages/';  // go back to inbox
        })
        .catch(error => {
            console.error('Clear conversation failed:', error);
            alert('Failed to clear conversation.');
            btn.disabled = false;
            btn.textContent = originalText;
        });
    });
});

// Client-side "time ago" in user's local time
document.querySelectorAll('.time-ago').forEach(el => {
    const timestamp = new Date(el.dataset.timestamp);
    const now = new Date();
    const diff = Math.floor((now - timestamp) / 1000); // seconds

    let text = '';
    if (diff < 60) text = 'just now';
    else if (diff < 3600) text = `${Math.floor(diff / 60)} minutes ago`;
    else if (diff < 86400) text = `${Math.floor(diff / 3600)} hours ago`;
    else text = `${Math.floor(diff / 86400)} days ago`;

    el.textContent = text;
});