def compile_db_sourcing(db: Session, df: pd.DataFrame, user_id: int, cycle_id: int,
                        file_name: str, file_hash: str):
    """
    Compile DB Sourcing dari uploaded file.
    - TETAP SIMPAN data meskipun ada warning
    - Hanya batalkan jika ada ERROR KRITIS (selain Sourcing Date kosong)
    - NaT akan diganti dengan date.today()
    """
    from core.validator import validate_db_sourcing_file
    
    errors = []
    imported = 0
    updated = 0
    warnings = []
    
    if db.is_active:
        db.rollback()
    
    # ============================================================
    # VALIDASI - TAPI TIDAK LANGSUNG RETURN
    # ============================================================
    valid_rows, val_errors = validate_db_sourcing_file(df, db, user_id)
    
    # Pisahkan warning dan error kritis
    critical_errors = []
    for err in val_errors:
        if err.get("warning", False):
            warnings.append(err)
        elif err.get("field") == "SUMMARY":
            # Skip summary error
            continue
        else:
            critical_errors.append(err)
    
    # Jika ada ERROR KRITIS (selain Sourcing Date), batalkan
    # TAPI jika hanya Sourcing Date yang error, tetap lanjutkan
    real_critical = []
    for err in critical_errors:
        if err.get("field") == "Sourcing Date" and "kosong" in str(err.get("error", "")):
            # Sourcing Date kosong dianggap warning, bukan error
            warnings.append(err)
        else:
            real_critical.append(err)
    
    if real_critical:
        db.rollback()
        return {
            "success": False,
            "imported": 0,
            "updated": 0,
            "errors": real_critical,
            "warnings": warnings
        }
    
    # ============================================================
    # PROSES DATA - TETAP LANJUTKAN
    # ============================================================
    
    if isinstance(valid_rows, pd.DataFrame):
        df = valid_rows.copy()
    
    for idx, row in df.iterrows():
        row_num = idx + 2
        
        kode_unik = safe_string_for_db(row.get('kode_unik', ''), max_length=100)
        nama = safe_string_for_db(row.get('nama', ''), max_length=255)
        
        # ============================================================
        # PERBAIKAN UTAMA: SOURCING DATE - CEK NaT JUGA!
        # ============================================================
        sourcing_date_raw = row.get('sourcing_date')
        
        # CEK: Apakah sourcing_date adalah NaT (Pandas Not a Time)
        is_nat = False
        try:
            if pd.isna(sourcing_date_raw) or (hasattr(sourcing_date_raw, 'isnull') and sourcing_date_raw.isnull()):
                is_nat = True
        except:
            pass
        
        # CEK: Apakah sourcing_date adalah NaT dari pandas
        if hasattr(sourcing_date_raw, '__class__') and 'NaT' in str(sourcing_date_raw.__class__):
            is_nat = True
        
        # Jika sourcing_date kosong, NaT, atau None, gunakan tanggal hari ini
        if sourcing_date_raw is None or is_nat or pd.isna(sourcing_date_raw):
            sourcing_date = datetime.now().date()
            warnings.append({
                "row": row_num,
                "field": "Sourcing Date",
                "value": sourcing_date_raw,
                "warning": True,
                "error": f"Sourcing Date kosong/NaT, otomatis diisi dengan {sourcing_date.strftime('%d/%m/%Y')}"
            })
        else:
            # Coba parse tanggal
            sourcing_date = safe_date(sourcing_date_raw)
            if not sourcing_date:
                sourcing_date = datetime.now().date()
                warnings.append({
                    "row": row_num,
                    "field": "Sourcing Date",
                    "value": sourcing_date_raw,
                    "warning": True,
                    "error": f"Format Sourcing Date tidak valid, otomatis diisi dengan {sourcing_date.strftime('%d/%m/%Y')}"
                })
        
        if not kode_unik:
            # Buat kode unik sementara
            kode_unik = f"UNKNOWN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}"
            warnings.append({
                "row": row_num,
                "field": "Kode Unik",
                "value": row.get('kode_unik'),
                "warning": True,
                "error": f"Kode Unik kosong, otomatis diisi dengan {kode_unik}"
            })
        
        if not nama:
            warnings.append({
                "row": row_num,
                "field": "Nama",
                "value": nama,
                "warning": True,
                "error": "Nama kosong, row di-skip"
            })
            continue
        
        try:
            # Cek existing
            existing = db.query(DBSourcing).filter(
                DBSourcing.kode_unik == kode_unik,
                DBSourcing.nama == nama
            ).first()
            
            # ============================================================
            # SAFE CONVERSIONS
            # ============================================================
            no_val = safe_int_value(row.get('no'), imported + 1)
            tahun_lulus_val = safe_int_value(row.get('tahun_lulus'))
            ipk_val = safe_numeric_value(row.get('ipk'))
            
            # String fields with truncation
            posisi_val = safe_string_for_db(row.get('posisi'), max_length=255)
            model_rekrutmen_val = safe_string_for_db(row.get('model_rekrutmen'), max_length=100)
            rekruter_val = safe_string_for_db(row.get('rekruter'), max_length=100)
            sumber_sourcing_val = safe_string_for_db(row.get('sumber_sourcing'), max_length=100)
            nama_univ_top10_val = safe_string_for_db(row.get('nama_universitas_top10'), max_length=255)
            nama_univ_lain_val = safe_string_for_db(row.get('nama_universitas_lainnya'), max_length=255)
            jenjang_val = safe_string_for_db(row.get('jenjang_pendidikan'), max_length=50)
            jurusan_val = safe_string_for_db(row.get('jurusan'), max_length=100)
            skor_inggris_val = safe_string_for_db(row.get('skor_bahasa_inggris'), max_length=50)
            university_tier_val = safe_string_for_db(row.get('university_tier'), max_length=20)
            ipk_tier_val = safe_string_for_db(row.get('ipk_tier'), max_length=20)
            nomor_hp_val = safe_string_for_db(row.get('nomor_hp'), max_length=20)
            email_val = safe_string_for_db(row.get('email'), max_length=255)
            domisili_val = safe_string_for_db(row.get('domisili'), max_length=100)
            last_position_val = safe_string_for_db(row.get('last_position'), max_length=255)
            last_company_val = safe_string_for_db(row.get('last_company'), max_length=255)
            last_tenure_val = safe_string_for_db(row.get('last_tenure'), max_length=50)
            total_tenure_val = safe_string_for_db(row.get('total_tenure'), max_length=50)
            pernah_di_fmcg_val = safe_string_for_db(row.get('pernah_di_fmcg'), max_length=10)
            
            # Detail fields
            sourcing_freelance_val = safe_string_for_db(row.get('sourcing_freelance'), max_length=3)
            
            # Boolean fields
            sourcing_hr_val = get_boolean_value(row.get('sourcing_hr'))
            shortlist_cv_val = get_boolean_value(row.get('shortlist_cv'))
            psikotes_val = get_boolean_value(row.get('psikotes'))
            hr_interview_val = get_boolean_value(row.get('hr_interview'))
            user_interview_val = get_boolean_value(row.get('user_interview'))
            offering_val = get_boolean_value(row.get('offering'))
            day1_val = get_boolean_value(row.get('day1'))
            
            # ============================================================
            # DATE FIELDS (pipeline stages) - CEK NaT JUGA!
            # ============================================================
            def safe_date_fallback(value):
                if value is None:
                    return None
                try:
                    if pd.isna(value):
                        return None
                except:
                    pass
                if hasattr(value, '__class__') and 'NaT' in str(value.__class__):
                    return None
                return safe_date(value)
            
            tanggal_sourcing_freelance = safe_date_fallback(row.get('tanggal_sourcing_freelance'))
            tanggal_sourcing = safe_date_fallback(row.get('tanggal_sourcing'))
            tanggal_shortlist_cv = safe_date_fallback(row.get('tanggal_shortlist_cv'))
            tanggal_psikotes = safe_date_fallback(row.get('tanggal_psikotes'))
            tanggal_hr_interview = safe_date_fallback(row.get('tanggal_hr_interview'))
            tanggal_user_interview = safe_date_fallback(row.get('tanggal_user_interview'))
            tanggal_offering = safe_date_fallback(row.get('tanggal_offering'))
            tanggal_day1 = safe_date_fallback(row.get('tanggal_day1'))
            tanggal_technical_test = safe_date_fallback(row.get('tanggal_technical_test'))
            tanggal_market_visit = safe_date_fallback(row.get('tanggal_market_visit'))
            tanggal_panel_interview = safe_date_fallback(row.get('tanggal_panel_interview'))
            tanggal_reference_check = safe_date_fallback(row.get('tanggal_reference_check'))
            tanggal_mcu = safe_date_fallback(row.get('tanggal_mcu'))
            
            # Detail keterangan
            detail_keterangan_sourcing_hr = safe_string_for_db(row.get('detail_keterangan_sourcing_hr'), max_length=500)
            detail_keterangan_shortlist_cv = safe_string_for_db(row.get('detail_keterangan_shortlist_cv'), max_length=500)
            detail_keterangan_psikotes = safe_string_for_db(row.get('detail_keterangan_psikotes'), max_length=500)
            detail_keterangan_hr_interview = safe_string_for_db(row.get('detail_keterangan_hr_interview'), max_length=500)
            detail_keterangan_user_interview = safe_string_for_db(row.get('detail_keterangan_user_interview'), max_length=500)
            detail_keterangan_offering = safe_string_for_db(row.get('detail_keterangan_offering'), max_length=500)
            detail_keterangan_day1 = safe_string_for_db(row.get('detail_keterangan_day1'), max_length=500)
            notes_val = safe_string_for_db(row.get('notes'), max_length=500)
            
            # Kode psikotes
            kode_psikotes_val = safe_string_for_db(row.get('kode_psikotes'), max_length=50)
            
            # Nilai psikotes
            nilai_logika_val = safe_string_for_db(row.get('nilai_logika'), max_length=20)
            nilai_iq_val = safe_string_for_db(row.get('nilai_iq'), max_length=20)
            nilai_daya_tangkap_val = safe_string_for_db(row.get('nilai_daya_tangkap'), max_length=20)
            nilai_ra_val = safe_string_for_db(row.get('nilai_ra'), max_length=20)
            disc_val = safe_string_for_db(row.get('disc'), max_length=20)
            
            # Technical test / case study
            technical_test_case_study_val = get_boolean_value(row.get('technical_test_case_study'))
            detail_keterangan_technical_test = safe_string_for_db(row.get('detail_keterangan_technical_test'), max_length=500)
            
            # Market visit
            market_visit_val = get_boolean_value(row.get('market_visit'))
            detail_market_visit = safe_string_for_db(row.get('detail_market_visit'), max_length=500)
            
            # Panel interview
            panel_interview_val = get_boolean_value(row.get('panel_interview'))
            detail_keterangan_panel_interview = safe_string_for_db(row.get('detail_keterangan_panel_interview'), max_length=500)
            
            # Reference check
            reference_check_val = get_boolean_value(row.get('reference_check'))
            detail_keterangan_reference_check = safe_string_for_db(row.get('detail_keterangan_reference_check'), max_length=500)
            
            # MCU
            mcu_val = get_boolean_value(row.get('mcu'))
            detail_keterangan_mcu = safe_string_for_db(row.get('detail_keterangan_mcu'), max_length=500)
            
            # ============================================================
            # BLACKLIST: Cek dari Excel (opsional)
            # ============================================================
            is_blacklisted = False
            blacklist_raw = row.get('is_blacklisted')
            if blacklist_raw is not None:
                if isinstance(blacklist_raw, bool):
                    is_blacklisted = blacklist_raw
                elif isinstance(blacklist_raw, str):
                    is_blacklisted = blacklist_raw.strip().upper() in ['YES', 'TRUE', 'Y', '1']
                elif isinstance(blacklist_raw, (int, float)):
                    is_blacklisted = bool(blacklist_raw)
            
            blacklist_reason = safe_string_for_db(row.get('blacklist_reason'), max_length=500)
            
            if existing:
                # UPDATE
                existing.no = no_val
                existing.sourcing_date = sourcing_date
                existing.kode_unik = kode_unik
                existing.posisi = posisi_val
                existing.model_rekrutmen = model_rekrutmen_val
                existing.rekruter = rekruter_val
                existing.sumber_sourcing = sumber_sourcing_val
                existing.nama = nama
                existing.nama_universitas_top10 = nama_univ_top10_val
                existing.nama_universitas_lainnya = nama_univ_lain_val
                existing.jenjang_pendidikan = jenjang_val
                existing.jurusan = jurusan_val
                existing.tahun_lulus = tahun_lulus_val
                existing.ipk = ipk_val
                existing.skor_bahasa_inggris = skor_inggris_val
                existing.university_tier = university_tier_val
                existing.ipk_tier = ipk_tier_val
                existing.nomor_hp = nomor_hp_val
                existing.email = email_val
                existing.domisili = domisili_val
                existing.last_position = last_position_val
                existing.last_company = last_company_val
                existing.last_tenure = last_tenure_val
                existing.total_tenure = total_tenure_val
                existing.pernah_di_fmcg = pernah_di_fmcg_val
                existing.sourcing_freelance = sourcing_freelance_val
                existing.sourcing_hr = sourcing_hr_val
                existing.shortlist_cv = shortlist_cv_val
                existing.psikotes = psikotes_val
                existing.hr_interview = hr_interview_val
                existing.user_interview = user_interview_val
                existing.offering = offering_val
                existing.day1 = day1_val
                # Pipeline dates
                existing.tanggal_sourcing_freelance = tanggal_sourcing_freelance
                existing.tanggal_sourcing = tanggal_sourcing
                existing.tanggal_shortlist_cv = tanggal_shortlist_cv
                existing.tanggal_psikotes = tanggal_psikotes
                existing.tanggal_hr_interview = tanggal_hr_interview
                existing.tanggal_user_interview = tanggal_user_interview
                existing.tanggal_offering = tanggal_offering
                existing.tanggal_day1 = tanggal_day1
                # Detail keterangan
                existing.detail_keterangan_sourcing_hr = detail_keterangan_sourcing_hr
                existing.detail_keterangan_shortlist_cv = detail_keterangan_shortlist_cv
                existing.detail_keterangan_psikotes = detail_keterangan_psikotes
                existing.detail_keterangan_hr_interview = detail_keterangan_hr_interview
                existing.detail_keterangan_user_interview = detail_keterangan_user_interview
                existing.detail_keterangan_offering = detail_keterangan_offering
                existing.detail_keterangan_day1 = detail_keterangan_day1
                existing.notes = notes_val
                # Psikotes
                existing.kode_psikotes = kode_psikotes_val
                existing.nilai_logika = nilai_logika_val
                existing.nilai_iq = nilai_iq_val
                existing.nilai_daya_tangkap = nilai_daya_tangkap_val
                existing.nilai_ra = nilai_ra_val
                existing.disc = disc_val
                # Technical test
                existing.technical_test_case_study = technical_test_case_study_val
                existing.detail_keterangan_technical_test = detail_keterangan_technical_test
                existing.tanggal_technical_test = tanggal_technical_test
                # Market visit
                existing.market_visit = market_visit_val
                existing.detail_market_visit = detail_market_visit
                existing.tanggal_market_visit = tanggal_market_visit
                # Panel interview
                existing.panel_interview = panel_interview_val
                existing.detail_keterangan_panel_interview = detail_keterangan_panel_interview
                existing.tanggal_panel_interview = tanggal_panel_interview
                # Reference check
                existing.reference_check = reference_check_val
                existing.detail_keterangan_reference_check = detail_keterangan_reference_check
                existing.tanggal_reference_check = tanggal_reference_check
                # MCU
                existing.mcu = mcu_val
                existing.detail_keterangan_mcu = detail_keterangan_mcu
                existing.tanggal_mcu = tanggal_mcu
                # Blacklist
                if is_blacklisted and not existing.is_blacklisted:
                    existing.is_blacklisted = True
                    existing.blacklisted_at = datetime.now()
                    existing.blacklisted_by = user_id
                    existing.blacklist_reason = blacklist_reason or 'Dari file upload'
                elif not is_blacklisted and existing.is_blacklisted:
                    existing.is_blacklisted = False
                    existing.blacklisted_at = None
                    existing.blacklisted_by = None
                    existing.blacklist_reason = None
                existing.last_updated_at = datetime.now()
                existing.last_compile_action = "UPDATE"
                updated += 1
            else:
                # INSERT
                new_sourcing = DBSourcing(
                    no=no_val,
                    sourcing_date=sourcing_date,
                    kode_unik=kode_unik,
                    posisi=posisi_val,
                    model_rekrutmen=model_rekrutmen_val,
                    rekruter=rekruter_val,
                    sumber_sourcing=sumber_sourcing_val,
                    nama=nama,
                    nama_universitas_top10=nama_univ_top10_val,
                    nama_universitas_lainnya=nama_univ_lain_val,
                    jenjang_pendidikan=jenjang_val,
                    jurusan=jurusan_val,
                    tahun_lulus=tahun_lulus_val,
                    ipk=ipk_val,
                    skor_bahasa_inggris=skor_inggris_val,
                    university_tier=university_tier_val,
                    ipk_tier=ipk_tier_val,
                    nomor_hp=nomor_hp_val,
                    email=email_val,
                    domisili=domisili_val,
                    last_position=last_position_val,
                    last_company=last_company_val,
                    last_tenure=last_tenure_val,
                    total_tenure=total_tenure_val,
                    pernah_di_fmcg=pernah_di_fmcg_val,
                    sourcing_freelance=sourcing_freelance_val,
                    sourcing_hr=sourcing_hr_val,
                    shortlist_cv=shortlist_cv_val,
                    psikotes=psikotes_val,
                    hr_interview=hr_interview_val,
                    user_interview=user_interview_val,
                    offering=offering_val,
                    day1=day1_val,
                    # Pipeline dates
                    tanggal_sourcing_freelance=tanggal_sourcing_freelance,
                    tanggal_sourcing=tanggal_sourcing,
                    tanggal_shortlist_cv=tanggal_shortlist_cv,
                    tanggal_psikotes=tanggal_psikotes,
                    tanggal_hr_interview=tanggal_hr_interview,
                    tanggal_user_interview=tanggal_user_interview,
                    tanggal_offering=tanggal_offering,
                    tanggal_day1=tanggal_day1,
                    # Detail keterangan
                    detail_keterangan_sourcing_hr=detail_keterangan_sourcing_hr,
                    detail_keterangan_shortlist_cv=detail_keterangan_shortlist_cv,
                    detail_keterangan_psikotes=detail_keterangan_psikotes,
                    detail_keterangan_hr_interview=detail_keterangan_hr_interview,
                    detail_keterangan_user_interview=detail_keterangan_user_interview,
                    detail_keterangan_offering=detail_keterangan_offering,
                    detail_keterangan_day1=detail_keterangan_day1,
                    notes=notes_val,
                    # Psikotes
                    kode_psikotes=kode_psikotes_val,
                    nilai_logika=nilai_logika_val,
                    nilai_iq=nilai_iq_val,
                    nilai_daya_tangkap=nilai_daya_tangkap_val,
                    nilai_ra=nilai_ra_val,
                    disc=disc_val,
                    # Technical test
                    technical_test_case_study=technical_test_case_study_val,
                    detail_keterangan_technical_test=detail_keterangan_technical_test,
                    tanggal_technical_test=tanggal_technical_test,
                    # Market visit
                    market_visit=market_visit_val,
                    detail_market_visit=detail_market_visit,
                    tanggal_market_visit=tanggal_market_visit,
                    # Panel interview
                    panel_interview=panel_interview_val,
                    detail_keterangan_panel_interview=detail_keterangan_panel_interview,
                    tanggal_panel_interview=tanggal_panel_interview,
                    # Reference check
                    reference_check=reference_check_val,
                    detail_keterangan_reference_check=detail_keterangan_reference_check,
                    tanggal_reference_check=tanggal_reference_check,
                    # MCU
                    mcu=mcu_val,
                    detail_keterangan_mcu=detail_keterangan_mcu,
                    tanggal_mcu=tanggal_mcu,
                    # Blacklist
                    is_blacklisted=is_blacklisted,
                    blacklisted_at=datetime.now() if is_blacklisted else None,
                    blacklisted_by=user_id if is_blacklisted else None,
                    blacklist_reason=blacklist_reason if is_blacklisted else None,
                    source_user_id=user_id,
                    source_cycle_id=cycle_id,
                    source_file=safe_string_for_db(file_name, max_length=255),
                    source_file_hash=safe_string_for_db(file_hash, max_length=64),
                    created_at=datetime.now(),
                    last_compile_action="INSERT"
                )
                db.add(new_sourcing)
                imported += 1
                
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
            db.rollback()
    
    # ============================================================
    # COMMIT
    # ============================================================
    if errors:
        db.rollback()
        return {
            "success": False,
            "imported": imported,
            "updated": updated,
            "errors": errors,
            "warnings": warnings
        }
    
    try:
        db.commit()
        return {
            "success": True,
            "imported": imported,
            "updated": updated,
            "errors": [],
            "warnings": warnings
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "imported": imported,
            "updated": updated,
            "errors": [str(e)],
            "warnings": warnings
        }
      
