import csv
import calendar
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from accounts.models import User
from accounts.decorators import boss_required
from audit.utils import log_action
from .models import ComplianceItem, ComplianceComment
from .forms import ComplianceMarkDoneForm, ComplianceCommentForm

def ensure_compliance_items_exist(year, month):
    """Ensure all compliance items exist for given month/year."""
    companies = [c[0] for c in ComplianceItem.COMPANY_CHOICES]
    types = [ComplianceItem.TDS_PAYMENT, ComplianceItem.GSTR_1, ComplianceItem.GSTR_3B]
    
    if month == 6:
        types.append(ComplianceItem.TDS_RETURN_Q1)
    elif month == 9:
        types.append(ComplianceItem.TDS_RETURN_Q2)
    elif month == 12:
        types.append(ComplianceItem.TDS_RETURN_Q3)
    elif month == 3:
        types.append(ComplianceItem.TDS_RETURN_Q4)
    
    created_count = 0
    for company in companies:
        for ctype in types:
            _, created = ComplianceItem.objects.get_or_create(
                company=company,
                compliance_type=ctype,
                month=month,
                year=year,
                defaults={'status': ComplianceItem.PENDING}
            )
            if created:
                created_count += 1
    return created_count

@login_required
def compliance_report_view(request, year=None, month=None):
    today = timezone.now().date()
    
    req_year = request.GET.get('year')
    req_month = request.GET.get('month')

    if year:
        selected_year = int(year)
    elif req_year:
        selected_year = int(req_year)
    else:
        # Default to previous month's year if current month is January
        selected_year = today.year - 1 if today.month == 1 else today.year

    if month:
        selected_month = int(month)
    elif req_month:
        selected_month = int(req_month)
    else:
        # Default to previous month (e.g., July when current month is August)
        selected_month = 12 if today.month == 1 else today.month - 1

    # Auto-generate items for selected month if missing
    ensure_compliance_items_exist(selected_year, selected_month)

    # Calculate prev/next month for navigation
    if selected_month == 1:
        prev_month, prev_year = 12, selected_year - 1
    else:
        prev_month, prev_year = selected_month - 1, selected_year

    if selected_month == 12:
        next_month, next_year = 1, selected_year + 1
    else:
        next_month, next_year = selected_month + 1, selected_year

    # Calculate compliance due dates (due in following month)
    if selected_month == 12:
        due_month = 1
        due_year = selected_year + 1
    else:
        due_month = selected_month + 1
        due_year = selected_year

    from datetime import date
    tds_due_date = date(due_year, due_month, 7)
    gstr1_due_date = date(due_year, due_month, 11)
    gstr3b_due_date = date(due_year, due_month, 20)

    is_tds_due_today = (today == tds_due_date)
    is_gstr1_due_today = (today == gstr1_due_date)
    is_gstr3b_due_today = (today == gstr3b_due_date)

    # Active compliance types for matrix display
    active_type_choices = [
        (ComplianceItem.TDS_PAYMENT, 'TDS Payment'),
        (ComplianceItem.GSTR_1, 'GSTR-1'),
        (ComplianceItem.GSTR_3B, 'GSTR-3B'),
    ]
    tds_qtr_due_date = None
    is_tds_qtr_due_today = False
    qtr_label = None

    if selected_month == 6:
        active_type_choices.append((ComplianceItem.TDS_RETURN_Q1, 'TDS Return Q1'))
        tds_qtr_due_date = date(selected_year, 7, 31)
        is_tds_qtr_due_today = (today == tds_qtr_due_date)
        qtr_label = 'TDS Return Q1'
    elif selected_month == 9:
        active_type_choices.append((ComplianceItem.TDS_RETURN_Q2, 'TDS Return Q2'))
        tds_qtr_due_date = date(selected_year, 10, 31)
        is_tds_qtr_due_today = (today == tds_qtr_due_date)
        qtr_label = 'TDS Return Q2'
    elif selected_month == 12:
        active_type_choices.append((ComplianceItem.TDS_RETURN_Q3, 'TDS Return Q3'))
        tds_qtr_due_date = date(selected_year + 1, 1, 31)
        is_tds_qtr_due_today = (today == tds_qtr_due_date)
        qtr_label = 'TDS Return Q3'
    elif selected_month == 3:
        active_type_choices.append((ComplianceItem.TDS_RETURN_Q4, 'TDS Return Q4'))
        tds_qtr_due_date = date(selected_year, 4, 30)
        is_tds_qtr_due_today = (today == tds_qtr_due_date)
        qtr_label = 'TDS Return Q4'

    # Query all compliance items for month
    items_qs = ComplianceItem.objects.filter(
        year=selected_year,
        month=selected_month
    ).select_related('completed_by').prefetch_related('comments', 'comments__boss')

    # Apply filters
    company_filter = request.GET.get('company', '').strip()
    type_filter = request.GET.get('compliance_type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    user_filter = request.GET.get('completed_by', '').strip()

    filtered_qs = items_qs
    if company_filter:
        filtered_qs = filtered_qs.filter(company=company_filter)
    if type_filter:
        filtered_qs = filtered_qs.filter(compliance_type=type_filter)
    if status_filter:
        filtered_qs = filtered_qs.filter(status=status_filter)
    if user_filter:
        filtered_qs = filtered_qs.filter(completed_by_id=user_filter)

    # Dashboard Summary Counts
    total_items = items_qs.count()
    completed_items = items_qs.filter(status=ComplianceItem.DONE).count()
    pending_items = items_qs.filter(status=ComplianceItem.PENDING).count()

    pending_by_company = {}
    for company_code, company_label in ComplianceItem.COMPANY_CHOICES:
        count = items_qs.filter(company=company_code, status=ComplianceItem.PENDING).count()
        pending_by_company[company_label] = count

    pending_by_type = {}
    for type_code, type_label in active_type_choices:
        count = items_qs.filter(compliance_type=type_code, status=ComplianceItem.PENDING).count()
        pending_by_type[type_label] = count

    # Build Matrix for UI rendering
    matrix_map = {}
    for item in filtered_qs:
        matrix_map[(item.company, item.compliance_type)] = item

    matrix_rows = []
    for company_code, company_label in ComplianceItem.COMPANY_CHOICES:
        cells = []
        for type_code, type_label in active_type_choices:
            item = matrix_map.get((company_code, type_code))
            cells.append({
                'type_code': type_code,
                'type_label': type_label,
                'item': item,
            })
        matrix_rows.append({
            'company_code': company_code,
            'company_label': company_label,
            'cells': cells,
        })

    all_users = User.objects.filter(is_active=True).order_by('full_name')

    context = {
        'selected_year': selected_year,
        'selected_month': selected_month,
        'month_name': calendar.month_name[selected_month],
        'due_month_name': calendar.month_name[due_month],
        'due_year': due_year,
        'tds_due_date': tds_due_date,
        'gstr1_due_date': gstr1_due_date,
        'gstr3b_due_date': gstr3b_due_date,
        'tds_qtr_due_date': tds_qtr_due_date,
        'is_tds_due_today': is_tds_due_today,
        'is_gstr1_due_today': is_gstr1_due_today,
        'is_gstr3b_due_today': is_gstr3b_due_today,
        'is_tds_qtr_due_today': is_tds_qtr_due_today,
        'qtr_label': qtr_label,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'total_items': total_items,
        'completed_items': completed_items,
        'pending_items': pending_items,
        'pending_by_company': pending_by_company,
        'pending_by_type': pending_by_type,
        'matrix_rows': matrix_rows,
        'company_choices': ComplianceItem.COMPANY_CHOICES,
        'type_choices': active_type_choices,
        'all_users': all_users,
        'company_filter': company_filter,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'user_filter': user_filter,
        'months_list': [(m, calendar.month_name[m]) for m in range(1, 13)],
        'years_list': list(range(today.year - 2, today.year + 3)),
    }
    return render(request, 'compliance/compliance_report.html', context)

@login_required
def compliance_detail_api(request, item_id):
    """Return compliance item details and comments as JSON."""
    item = get_object_or_404(
        ComplianceItem.objects.select_related('completed_by').prefetch_related('comments', 'comments__boss'),
        id=item_id
    )

    comments_data = [
        {
            'id': c.id,
            'boss_name': c.boss.full_name or c.boss.username,
            'comment': c.comment,
            'created_at': c.created_at.strftime('%b %d, %Y %I:%M %p')
        }
        for c in item.comments.all()
    ]

    data = {
        'id': item.id,
        'company_display': item.get_company_display(),
        'type_display': item.get_compliance_type_display(),
        'month_year': f"{calendar.month_name[item.month]} {item.year}",
        'status': item.status,
        'status_display': item.get_status_display(),
        'completed_by_name': item.completed_by.full_name if item.completed_by else None,
        'completed_at_formatted': item.completed_at.strftime('%b %d, %Y %I:%M %p') if item.completed_at else None,
        'reference_number': item.reference_number,
        'remarks': item.remarks,
        'document_link': item.document_link,
        'comments': comments_data,
    }
    return JsonResponse(data)

@login_required
def compliance_mark_done_view(request, item_id):
    """Mark a pending compliance item as DONE. Restricted to Employees (Boss has view-only access)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    if request.user.is_boss:
        raise PermissionDenied("Boss users have view-only access to compliance reports.")

    with transaction.atomic():
        try:
            item = ComplianceItem.objects.select_for_update().get(id=item_id)
        except ComplianceItem.DoesNotExist:
            messages.error(request, "Compliance item not found.")
            return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

        if item.status in [ComplianceItem.DONE, ComplianceItem.NOT_APPLICABLE]:
            messages.warning(
                request,
                f"This compliance item was already completed or marked as {item.get_status_display()}."
            )
            return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

        remarks = request.POST.get('remarks', '').strip()

        item.status = ComplianceItem.DONE
        item.completed_by = request.user
        item.completed_at = timezone.now()
        item.remarks = remarks
        item.save()

    log_action(
        request.user,
        'COMPLIANCE_MARKED_DONE',
        'ComplianceItem',
        item.id,
        f"Marked {item.get_company_display()} - {item.get_compliance_type_display()} ({item.month}/{item.year}) as Done."
    )
    messages.success(request, f"Compliance item for {item.get_company_display()} ({item.get_compliance_type_display()}) successfully marked as DONE!")
    return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

@login_required
def compliance_mark_na_view(request, item_id):
    """Mark a pending compliance item as NOT_APPLICABLE (N/A). Restricted to Helper employees."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    if request.user.is_boss or not request.user.is_helper:
        raise PermissionDenied("Only Helper employees can mark compliance items as N/A.")

    with transaction.atomic():
        try:
            item = ComplianceItem.objects.select_for_update().get(id=item_id)
        except ComplianceItem.DoesNotExist:
            messages.error(request, "Compliance item not found.")
            return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

        if item.status in [ComplianceItem.DONE, ComplianceItem.NOT_APPLICABLE]:
            messages.warning(
                request,
                f"This compliance item was already updated as {item.get_status_display()}."
            )
            return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

        remarks = request.POST.get('remarks', '').strip()

        item.status = ComplianceItem.NOT_APPLICABLE
        item.completed_by = request.user
        item.completed_at = timezone.now()
        item.remarks = remarks
        item.save()

    log_action(
        request.user,
        'COMPLIANCE_MARKED_NA',
        'ComplianceItem',
        item.id,
        f"Marked {item.get_company_display()} - {item.get_compliance_type_display()} ({item.month}/{item.year}) as N/A."
    )
    messages.info(request, f"Compliance item for {item.get_company_display()} ({item.get_compliance_type_display()}) marked as N/A.")
    return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

@login_required
@boss_required
def compliance_comment_add_view(request, item_id):
    """Boss-only view to add comment to a compliance item."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    item = get_object_or_404(ComplianceItem, id=item_id)
    comment_text = request.POST.get('comment', '').strip()

    if not comment_text:
        messages.error(request, "Comment text cannot be empty.")
        return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

    comment = ComplianceComment.objects.create(
        compliance_item=item,
        boss=request.user,
        comment=comment_text
    )

    log_action(
        request.user,
        'COMPLIANCE_COMMENT_ADDED',
        'ComplianceItem',
        item.id,
        f"Added Boss comment on compliance item {item.get_company_display()} - {item.get_compliance_type_display()}."
    )
    messages.success(request, "Boss comment added to compliance item.")
    return redirect(request.META.get('HTTP_REFERER', 'compliance:compliance_report'))

@login_required
def compliance_export_csv_view(request, year, month):
    """Export compliance matrix report to CSV file."""
    ensure_compliance_items_exist(year, month)
    items = ComplianceItem.objects.filter(year=year, month=month).select_related('completed_by')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Gemini_Compliance_{year}_{month:02d}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Month/Year', 'Company', 'Compliance Type', 'Status', 'Completed By', 'Completed At', 'Reference Number', 'Remarks', 'Document Link'])

    for item in items:
        writer.writerow([
            f"{calendar.month_name[month]} {year}",
            item.get_company_display(),
            item.get_compliance_type_display(),
            item.get_status_display(),
            item.completed_by.full_name if item.completed_by else '—',
            item.completed_at.strftime('%Y-%m-%d %H:%M:%S') if item.completed_at else '—',
            item.reference_number or '—',
            item.remarks or '—',
            item.document_link or '—'
        ])

    return response

@login_required
def compliance_export_excel_view(request, year, month):
    """Export compliance matrix report to Excel (.xlsx) file using openpyxl."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    ensure_compliance_items_exist(year, month)
    items = ComplianceItem.objects.filter(year=year, month=month).select_related('completed_by')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Compliance {calendar.month_name[month]} {year}"

    # Header title
    ws.merge_cells('A1:I1')
    title_cell = ws['A1']
    title_cell.value = f"Gemini Updates - Monthly Compliance Report ({calendar.month_name[month]} {year})"
    title_cell.font = Font(name='Calibri', size=16, bold=True, color='FFFFFF')
    title_cell.fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 35

    # Table Headers
    headers = ['S.No', 'Company', 'Compliance Type', 'Status', 'Completed By', 'Completed At', 'Ref / Challan #', 'Remarks', 'Doc URL']
    ws.append([]) # Row 2 empty spacer
    ws.append(headers) # Row 3 headers

    header_fill = PatternFill(start_color='3B82F6', end_color='3B82F6', fill_type='solid')
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')

    for col_num in range(1, 10):
        cell = ws.cell(row=3, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[3].height = 25

    # Data Rows
    row_num = 4
    for idx, item in enumerate(items, 1):
        ws.append([
            idx,
            item.get_company_display(),
            item.get_compliance_type_display(),
            item.get_status_display(),
            item.completed_by.full_name if item.completed_by else '—',
            item.completed_at.strftime('%Y-%m-%d %H:%M') if item.completed_at else '—',
            item.reference_number or '—',
            item.remarks or '—',
            item.document_link or '—'
        ])
        
        # Color coding status
        status_cell = ws.cell(row=row_num, column=4)
        if item.status == ComplianceItem.DONE:
            status_cell.fill = PatternFill(start_color='DCFCE7', end_color='DCFCE7', fill_type='solid')
            status_cell.font = Font(color='166534', bold=True)
        else:
            status_cell.fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid')
            status_cell.font = Font(color='92400E', bold=True)
            
        row_num += 1

    # Auto-fit column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Gemini_Compliance_{year}_{month:02d}.xlsx"'
    wb.save(response)
    return response

@login_required
def compliance_print_view(request, year, month):
    """Printable compliance matrix view."""
    ensure_compliance_items_exist(year, month)
    items_qs = ComplianceItem.objects.filter(year=year, month=month).select_related('completed_by')
    
    matrix_map = {(item.company, item.compliance_type): item for item in items_qs}
    matrix_rows = []
    for company_code, company_label in ComplianceItem.COMPANY_CHOICES:
        cells = []
        for type_code, type_label in ComplianceItem.COMPLIANCE_TYPE_CHOICES:
            cells.append(matrix_map.get((company_code, type_code)))
        matrix_rows.append({
            'company_label': company_label,
            'cells': cells,
        })

    context = {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'matrix_rows': matrix_rows,
        'type_choices': ComplianceItem.COMPLIANCE_TYPE_CHOICES,
        'printed_at': timezone.now(),
    }
    return render(request, 'compliance/compliance_print.html', context)
