// static/js/dashboard.js

// Dashboard-specific functionality
class DashboardManager {
    constructor() {
        this.initCharts();
        this.initNotifications();
        this.initQuickActions();
        this.initStudentManagement();
    }

    initCharts() {
        // Initialize charts if Chart.js is available
        if (typeof Chart !== 'undefined') {
            this.initProgressChart();
            this.initActivityChart();
        }
    }

    initProgressChart() {
        const ctx = document.getElementById('progressChart');
        if (!ctx) return;

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Signed Notes', 'Pending Notes'],
                datasets: [{
                    data: [
                        parseInt(document.querySelector('.signed-count').textContent || 0),
                        parseInt(document.querySelector('.pending-count').textContent || 0)
                    ],
                    backgroundColor: [
                        'rgba(40, 167, 69, 0.8)',
                        'rgba(255, 193, 7, 0.8)'
                    ],
                    borderColor: [
                        'rgba(40, 167, 69, 1)',
                        'rgba(255, 193, 7, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    initActivityChart() {
        const ctx = document.getElementById('activityChart');
        if (!ctx) return;

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Notes Created',
                    data: [12, 19, 3, 5, 2, 3, 8],
                    backgroundColor: 'rgba(67, 97, 238, 0.1)',
                    borderColor: 'rgba(67, 97, 238, 1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 2
                        }
                    }
                }
            }
        });
    }

    initNotifications() {
        // Check for new notifications
        if (Notification.permission === 'granted') {
            this.checkNotifications();
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    this.checkNotifications();
                }
            });
        }
    }

    async checkNotifications() {
        try {
            const response = await fetch('/api/notifications');
            const data = await response.json();

            data.forEach(notification => {
                this.showNotification(notification);
            });
        } catch (error) {
            console.error('Failed to fetch notifications:', error);
        }
    }

    showNotification(notification) {
        if (!('Notification' in window)) return;

        const options = {
            body: notification.message,
            icon: '/static/favicon.ico',
            badge: '/static/favicon.ico'
        };

        const notif = new Notification(notification.title, options);

        notif.onclick = () => {
            window.focus();
            notif.close();
            if (notification.url) {
                window.location.href = notification.url;
            }
        };
    }

    initQuickActions() {
        // Quick add note
        document.querySelectorAll('.quick-add-note').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const studentId = btn.dataset.studentId;

                // Redirect to add note page
                window.location.href = `/note/add/${studentId}`;
            });
        });

        // Quick view student
        document.querySelectorAll('.quick-view-student').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const studentId = btn.dataset.studentId;

                // Show student modal
                this.showStudentModal(studentId);
            });
        });
    }

    async showStudentModal(studentId) {
        try {
            const response = await fetch(`/api/student/${studentId}`);
            const student = await response.json();

            const modalHtml = `
                <div class="modal fade" id="studentModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">${student.full_name}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <p><strong>Email:</strong> ${student.email}</p>
                                <p><strong>Phone:</strong> ${student.phone}</p>
                                <p><strong>Grade Level:</strong> ${student.grade_level}</p>
                                <p><strong>Total Notes:</strong> ${student.total_notes}</p>
                            </div>
                            <div class="modal-footer">
                                <a href="/student/${studentId}/notes" class="btn btn-primary">
                                    View All Notes
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal
            const existingModal = document.getElementById('studentModal');
            if (existingModal) existingModal.remove();

            // Add new modal
            document.body.insertAdjacentHTML('beforeend', modalHtml);

            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('studentModal'));
            modal.show();
        } catch (error) {
            window.appUtils.showToast('Failed to load student information', 'danger');
        }
    }

    initStudentManagement() {
        // Add student functionality
        const addStudentForm = document.querySelector('#addStudentForm');
        if (addStudentForm) {
            addStudentForm.addEventListener('submit', async (e) => {
                e.preventDefault();

                const formData = new FormData(addStudentForm);
                const username = formData.get('username');

                try {
                    const result = await window.appUtils.apiRequest(
                        '/api/students/add',
                        'POST',
                        { username }
                    );

                    window.appUtils.showToast(result.message, 'success');

                    // Reload page after 1 second
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);

                } catch (error) {
                    window.appUtils.showToast(error.message, 'danger');
                }
            });
        }

        // Student search
        const studentSearch = document.querySelector('#studentSearch');
        if (studentSearch) {
            studentSearch.addEventListener('input', this.debounce(async (e) => {
                const searchTerm = e.target.value;

                if (searchTerm.length < 2) return;

                try {
                    const result = await window.appUtils.apiRequest(
                        `/api/students/search?q=${encodeURIComponent(searchTerm)}`,
                        'GET'
                    );

                    this.displaySearchResults(result.students);
                } catch (error) {
                    console.error('Search failed:', error);
                }
            }, 300));
        }
    }

    displaySearchResults(students) {
        const resultsContainer = document.querySelector('#searchResults');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = '';

        if (students.length === 0) {
            resultsContainer.innerHTML = '<div class="text-center text-muted py-3">No students found</div>';
            return;
        }

        students.forEach(student => {
            const studentItem = document.createElement('div');
            studentItem.className = 'list-group-item list-group-item-action';
            studentItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${student.full_name}</strong>
                        <div class="text-muted small">@${student.username}</div>
                    </div>
                    <button class="btn btn-sm btn-outline-primary add-student-btn"
                            data-student-id="${student.id}">
                        Add
                    </button>
                </div>
            `;

            resultsContainer.appendChild(studentItem);
        });

        // Add event listeners to add buttons
        resultsContainer.querySelectorAll('.add-student-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const studentId = btn.dataset.studentId;
                this.addStudentToTeacher(studentId);
            });
        });
    }

    async addStudentToTeacher(studentId) {
        try {
            const result = await window.appUtils.apiRequest(
                '/api/students/add',
                'POST',
                { student_id: studentId }
            );

            window.appUtils.showToast(result.message, 'success');

            // Hide search results
            document.querySelector('#searchResults').innerHTML = '';
            document.querySelector('#studentSearch').value = '';

            // Reload page after 1 second
            setTimeout(() => {
                window.location.reload();
            }, 1000);

        } catch (error) {
            window.appUtils.showToast(error.message, 'danger');
        }
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize dashboard manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.dashboard-page')) {
        new DashboardManager();
    }
});