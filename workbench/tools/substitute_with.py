def substitute_with(*, to_delete, keep):
    """
    Substitute the first argument with the second in all relations,
    and delete the first argument afterwards.
    """
    assert to_delete.__class__ == keep.__class__
    assert to_delete.pk != keep.pk

    fields = [
        f
        for f in to_delete._meta.get_fields()
        if (f.one_to_many or f.one_to_one) and f.auto_created and not f.concrete
    ]

    for related_object in fields:
        queryset = related_object.related_model._base_manager.complex_filter(
            {related_object.field.name: to_delete.pk}
        )

        queryset.update(**{related_object.field.name: keep.pk})
    to_delete.delete()
